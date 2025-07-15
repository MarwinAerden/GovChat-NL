<script lang="ts">    import { WEBUI_BASE_URL } from '$lib/constants';
    import { models, settings, user } from '$lib/stores';
    import { filteredModels, currentAppContext } from '$lib/stores/appModels';
    import { toast } from 'svelte-sonner';
    import { fade } from 'svelte/transition';
    import { onMount } from 'svelte';
    import { subsidyStore, fetchSavedOutputs, initializeStore, setSelectedOutput, addSavedOutput, clearSavedOutputs, saveSelection, loadLastSelection, setGlobalSelection, loadGlobalSelection } from '$lib/stores/subsidyStore';
    import type { SubsidyResponse } from '$lib/stores/subsidyStore';
    import Modal from '$lib/components/common/Modal.svelte';
    import { browser } from '$app/environment';

    // Modal control variable
    let showInfoModal = false;

    let userInput: string = '';
    let responseData: SubsidyResponse | null = null;
    let isLoading: boolean = false;
    let error: string | null = null;

    let fileInput: HTMLInputElement;
    let isProcessingFile = false;
    let isFlashing = false;
    let fileProcessingProgress = 0;
    let fileProcessingInterval: ReturnType<typeof setInterval> | null = null;

    // Edit mode variables
    let isEditMode = false;
    let editableCriteria: {id: number, text: string}[] = [];
    let editableSummary = '';

    // Use filtered models from store instead of manual filtering
    $: subsidieAccessibleModels = $filteredModels;

    // Function to get the first available subsidie model
    function getFirstSubsidieModel() {
        return subsidieAccessibleModels.length > 0 ? subsidieAccessibleModels[0].id : null;
    }

    onMount(async () => {
        // Initialiseer expliciet bij het laden
        initializeStore();
        
        try {
            // Haal eerst alle opgeslagen criteria op
            await fetchSavedOutputs();
            
            // Probeer eerst de globale selectie te laden
            const globalSelection = await loadGlobalSelection();
            
            if (globalSelection) {
                console.log("Globale standaard selectie geladen:", globalSelection.name);
                toast.success(`Globale standaard selectie "${globalSelection.name}" geladen`);
                return; // Stop hier als er een globale selectie is
            }
            
            // Als er geen globale selectie is, probeer dan de persoonlijke selectie
            const lastSelection = await loadLastSelection();
            if (lastSelection) {
                console.log("Persoonlijke selectie geladen:", lastSelection.name);
                toast.success(`Selectie "${lastSelection.name}" geladen`);
            }        } catch (error) {
            console.error("Fout bij laden van selecties:", error);
            toast.error("Kon selecties niet laden");
        }

        // Show info modal on first visit
        if (browser) {
            const tutorialShown = localStorage.getItem('subsidieTutorialShown');
            if (!tutorialShown) {
                showInfoModal = true;
                localStorage.setItem('subsidieTutorialShown', 'true');
            }
        }
    });

    async function handleSubmit() {
        if (!userInput.trim()) {
            error = 'Voer alstublieft de regeling in.';
            toast.error(error);
            return;
        }
        
        let currentModelId = $settings?.models?.[0];
        
        // Check if current model has subsidie access, if not use first available subsidie model
        if (currentModelId) {
            const modelHasSubsidieAccess = subsidieAccessibleModels.some(m => m.id === currentModelId);
            if (!modelHasSubsidieAccess) {
                currentModelId = getFirstSubsidieModel();
                if (currentModelId) {
                    toast.warn(`Het geselecteerde model heeft geen toegang tot de subsidie app. Gebruikt alternatief model.`);
                }
            }
        } else {
            currentModelId = getFirstSubsidieModel();
        }
        
        if (!currentModelId) {
            error = 'Er zijn geen modellen beschikbaar voor de subsidie app. Neem contact op met de administrator.';
            toast.error(error);
            return;
        }
        isLoading = true;
        error = null;
        responseData = null;
        setSelectedOutput(null);
        try {
            const backendUrl = WEBUI_BASE_URL || 'http://localhost:8080';
            const res = await fetch(`${backendUrl}/api/subsidies/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify({
                    user_input: userInput,
                    model: currentModelId
                })
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({ detail: 'Onbekende fout' }));
                throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
            }
            responseData = await res.json();
        } catch (e: any) {
            console.error('Fout bij ophalen subsidie-Criteria:', e);
            error = `Er is een fout opgetreden: ${e.message || 'Kon de server niet bereiken.'}`;
            toast.error(error);
        } finally {
            isLoading = false;
        }
    }

    async function handleFileUpload(event: Event | DragEvent) {
        let file: File | null = null;

        if (event instanceof DragEvent && event.dataTransfer?.files) {
            file = event.dataTransfer.files[0];
        } else if (event.target instanceof HTMLInputElement && event.target.files) {
            file = event.target.files[0];
        }

        if (!file) return;

        if (!file.name.match(/\.(doc|docx|pdf|txt|rtf)$/i)) {
            toast.error('Alleen Word, PDF, TXT of RTF bestanden zijn toegestaan');
            return;
        }

        isProcessingFile = true;
        isFlashing = true;
        fileProcessingProgress = 0;
        if (fileProcessingInterval) clearInterval(fileProcessingInterval);

        fileProcessingInterval = setInterval(() => {
            if (fileProcessingProgress < 99) {
                fileProcessingProgress += 1;
            } else {
                if (fileProcessingInterval) clearInterval(fileProcessingInterval);
                fileProcessingInterval = null;
            }
        }, 30);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const uploadResponse = await fetch(`${WEBUI_BASE_URL}/api/v1/files`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: formData
            });

            if (!uploadResponse.ok) {
                const errorData = await uploadResponse.json().catch(() => ({ detail: 'Fout bij uploaden bestand' }));
                throw new Error(errorData.detail || 'Fout bij uploaden bestand');
            }

            const uploadData = await uploadResponse.json();

            if (uploadData.content) {
                userInput = uploadData.content;
            } else if (uploadData.id) {
                const contentResponse = await fetch(`${WEBUI_BASE_URL}/api/v1/files/${uploadData.id}/data/content`, {
                    method: 'GET',
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
                });
                if (!contentResponse.ok) {
                    throw new Error('Fout bij ophalen bestandsinhoud na upload');
                }
                const textData = await contentResponse.json();
                userInput = textData.content;
            } else {
                throw new Error('Onbekend antwoordformaat van upload endpoint');
            }

            toast.success('Bestand succesvol geüpload en inhoud ingevoegd.');

        } catch (err: any) {
            console.error('Error processing file:', err);
            toast.error(`Fout bij verwerken bestand: ${err.message}`);
            userInput = '';
        } finally {
            if (fileProcessingInterval) clearInterval(fileProcessingInterval);
            fileProcessingInterval = null;
            fileProcessingProgress = 100;
            isProcessingFile = false;

            if (fileInput) fileInput.value = '';

            setTimeout(() => {
                isFlashing = false;
            }, 1000);
        }
    }

    function saveCurrentOutput() {
        if (responseData) {
            const name = prompt("Geef een naam op voor deze opgeslagen versie:", `Resultaat ${new Date().toLocaleTimeString()}`);
            if (name === null) {
                toast.info("Opslaan geannuleerd.");
                return;
            }
            if (!name.trim()) {
                toast.error("Naam mag niet leeg zijn.");
                return;
            }

            addSavedOutput({
                ...responseData,
                name: name.trim()
            });
            toast.success(`Resultaat "${name.trim()}" opgeslagen (Totaal: ${$subsidyStore.savedOutputs.length})`);
            console.log("Opgeslagen outputs (Store):", $subsidyStore.savedOutputs);
        } else {
            toast.info('Er is geen resultaat om op te slaan.');
        }
    }

    function startEditMode() {
        if (responseData) {
            isEditMode = true;
            editableCriteria = [...responseData.criteria];
            editableSummary = responseData.summary || '';
            toast.info("Edit-modus geactiveerd. U kunt nu de criteria aanpassen.");
        }
    }

    function saveEditedCriteria() {
        if (editableCriteria.length === 0) {
            toast.error("Er moeten minimaal criteria aanwezig zijn.");
            return;
        }

        const name = prompt("Geef een naam op voor deze aangepaste versie:", `Aangepast ${new Date().toLocaleTimeString()}`);
        if (name === null) {
            toast.info("Opslaan geannuleerd.");
            return;
        }
        if (!name.trim()) {
            toast.error("Naam mag niet leeg zijn.");
            return;
        }

        // Update responseData met de aangepaste criteria
        responseData = {
            criteria: editableCriteria,
            summary: editableSummary,
            savedId: `edited_${Date.now()}`,
            timestamp: new Date().toISOString(),
            name: name.trim()
        };

        addSavedOutput(responseData);
        toast.success(`Aangepaste versie "${name.trim()}" opgeslagen!`);
        
        // Exit edit mode
        isEditMode = false;
    }

    function cancelEdit() {
        isEditMode = false;
        editableCriteria = [];
        editableSummary = '';
        toast.info("Edit-modus geannuleerd.");
    }

    function addCriterion() {
        const newId = editableCriteria.length > 0 ? Math.max(...editableCriteria.map(c => c.id)) + 1 : 1;
        editableCriteria = [...editableCriteria, { id: newId, text: '' }];
    }

    function removeCriterion(index: number) {
        editableCriteria = editableCriteria.filter((_, i) => i !== index);
    }

    function selectOutput(output: SubsidyResponse) {
        // Selecteer zonder persistent te maken
        setSelectedOutput(output, false);
        toast.success(`"${output.name}" geselecteerd voor deze sessie.`);
        console.log("Geselecteerde output (Store):", $subsidyStore.selectedOutput);
    }

    function handleClearOutputs() {
        clearSavedOutputs();
        toast.info('Opgeslagen resultaten gewist.');
    }

    async function handleSaveSelection() {
        if ($subsidyStore.selectedOutput) {
            try {
                // Controleer eerst of deze selectie al is opgeslagen
                const existingItem = $subsidyStore.savedOutputs.find(item => 
                    item.savedId === $subsidyStore.selectedOutput?.savedId);
                
                if (existingItem) {
                    toast.info("Deze selectie is al opgeslagen");
                    return;
                }
                
                const name = prompt("Geef een naam voor deze selectie:", 
                    $subsidyStore.selectedOutput.name || `Selectie ${new Date().toLocaleTimeString()}`);
                
                if (name === null) {
                    toast.info("Opslaan van selectie geannuleerd");
                    return;
                }
                
                const savedSelection = await saveSelection({
                    ...$subsidyStore.selectedOutput,
                    name: name.trim() || $subsidyStore.selectedOutput.name
                });
                
                toast.success(`Selectie "${name || 'Naamloos'}" opgeslagen in backend`);
                console.log("Opgeslagen selectie:", savedSelection);
            } catch (error) {
                console.error("Fout bij opslaan selectie:", error);
                toast.error(`Kon selectie niet opslaan: ${error.message}`);
            }
        } else {
            toast.error("Er is geen selectie om op te slaan");
        }
    }

    async function setAsGlobalStandard() {
        if (!$subsidyStore.selectedOutput) {
            toast.error("Selecteer eerst criteria om als standaard in te stellen");
            return;
        }

        try {
            const isAdmin = $user?.role === 'admin';
            if (!isAdmin) {
                toast.error("Alleen beheerders kunnen de standaard criteria instellen");
                return;
            }

            const success = await setGlobalSelection($subsidyStore.selectedOutput);
            
            if (success) {
                toast.success(`"${$subsidyStore.selectedOutput.name}" is nu de standaard selectie voor alle gebruikers`);
            } else {
                toast.error("Kon de selectie niet als standaard instellen");
            }
        } catch (error) {
            console.error("Fout bij instellen globale standaard:", error);
            toast.error(`Kon de standaard selectie niet instellen: ${error.message}`);
        }
    }
</script>

<div class="max-w-7xl mx-auto mt-6 space-y-6 px-4">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">            <div class="flex justify-between items-center mb-6">
                <div class="flex items-center gap-2">
                    <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
                        Admin Panel Subsidie Criteria
                    </h2>
                    <!-- Add info button next to the title -->
                    <button
                        type="button"
                        on:click={() => showInfoModal = true}
                        class="bg-blue-100 hover:bg-blue-200 dark:bg-blue-700 dark:hover:bg-blue-600 text-blue-700 dark:text-blue-200 font-medium py-1.5 px-3 rounded-md focus:outline-none focus:shadow-outline flex items-center gap-1.5"
                        aria-label="Uitleg over de subsidie criteria tool"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>Uitleg</span>
                    </button>
                </div>
            </div>

            <form on:submit|preventDefault={handleSubmit} class="space-y-4">
                <div>
                    <label for="subsidy-input" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Uw Regeling (of upload een bestand)
                    </label>
                    <div class="relative">
                        {#if isProcessingFile}
                            <div class="progress-line absolute inset-x-0 top-0 h-1 pointer-events-none overflow-hidden z-10">
                                <div class="line"></div>
                            </div>
                        {/if}
                        <textarea
                            id="subsidy-input"
                            bind:value={userInput}
                            placeholder="Voer hier uw gehele subsidieregeling in..."
                            rows="5"
                            disabled={isLoading || isProcessingFile}
                            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-50 dark:bg-gray-700 dark:border-gray-600 dark:text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 disabled:opacity-50 font-[system-ui] {isFlashing ? 'flash-animation' : ''}"
                            on:dragover|preventDefault
                            on:drop|preventDefault={handleFileUpload}
                        />
                        <div class="mt-2">
                            {#if isProcessingFile || fileProcessingProgress === 100}
                                <div class="flex items-center gap-2" transition:fade={{ duration: 150 }}>
                                    <div class="flex-grow bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                        <div
                                            class="bg-blue-600 h-2 rounded-full transition-all duration-150 ease-linear"
                                            style="width: {fileProcessingProgress}%"
                                        ></div>
                                    </div>
                                    <span class="text-sm text-gray-600 dark:text-gray-400 min-w-[3rem] text-right">{fileProcessingProgress}%</span>
                                </div>
                            {/if}
                            <div class="mt-2 flex items-center justify-between gap-2">
                                <div class="flex items-center gap-2">
                                    <input
                                        type="file"
                                        accept=".doc,.docx,.pdf,.txt,.rtf"
                                        class="hidden"
                                        bind:this={fileInput}
                                        on:change={handleFileUpload}
                                    />
                                    <button
                                        type="button"
                                        on:click={() => fileInput.click()}
                                        disabled={isProcessingFile || isLoading}
                                        class="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-white font-medium py-1 px-3 rounded focus:outline-none focus:shadow-outline flex items-center gap-2 disabled:opacity-50"
                                    >
                                        {#if isProcessingFile}
                                            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                            <span>Uploaden...</span>
                                        {:else if !isProcessingFile && fileProcessingProgress === 100}
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                            <span>Bestand geüpload</span>
                                        {:else}
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3 3m0 0l-3-3m3 3V8" /></svg>
                                            <span>Upload bestand</span>
                                        {/if}
                                    </button>
                                </div>
                                <span class="text-sm text-gray-500 dark:text-gray-400 text-right">
                                    of sleep bestand hierheen<br>(Word, PDF, TXT, RTF)
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={isLoading || isProcessingFile || !userInput.trim()}
                    class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                    {#if isLoading}
                        <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        Verwerken...
                    {:else if isProcessingFile}
                        Bestand verwerken...
                    {:else if !userInput.trim()}
                        Voer eerst subsidieregeling in
                    {:else}
                        Haal relevante Criteria uit subsidieregelingen
                    {/if}
                </button>
            </form>
        </div>

        {#if $subsidyStore.savedOutputs.length > 0}
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
                <h3 class="text-xl font-bold text-gray-800 dark:text-white mb-4">Opgeslagen Resultaten ({$subsidyStore.savedOutputs.length})</h3>
                <ul class="space-y-3 max-h-[calc(100vh-20rem)] overflow-y-auto pr-2">
                    {#each $subsidyStore.savedOutputs.filter(output => 
                        output.criteria && 
                        output.criteria.length > 0 && 
                        (!output.name.includes("Naamloos") || output.criteria.length > 0)
                    ) as savedOutput (savedOutput.savedId)}
                        <li class="border border-gray-200 dark:border-gray-700 rounded p-3 flex justify-between items-center {$subsidyStore.selectedOutput?.savedId === savedOutput.savedId ? 'bg-blue-100 dark:bg-blue-900/50 ring-2 ring-blue-500' : 'bg-gray-50 dark:bg-gray-700/50'}">
                            <div>
                                <p class="font-semibold text-gray-800 dark:text-gray-200">
                                    {savedOutput.name || 'Resultaat'}
                                </p>
                                <p class="text-sm text-gray-500 dark:text-gray-400">
                                    Opgeslagen: {savedOutput.timestamp?.toLocaleString() ?? 'Onbekend'}
                                    ({savedOutput.criteria.length} criteria)
                                </p>
                            </div>                            <button
                                type="button"
                                on:click={() => selectOutput(savedOutput)}
                                class="ml-4 px-3 py-1 text-sm rounded focus:outline-none focus:ring-2 focus:ring-offset-1 whitespace-nowrap min-w-[120px] {$subsidyStore.selectedOutput?.savedId === savedOutput.savedId ? 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500' : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500 focus:ring-gray-400'}"
                                title="Selecteer dit resultaat om te gebruiken"
                            >
                                {$subsidyStore.selectedOutput?.savedId === savedOutput.savedId ? 'Geselecteerd' : 'Selecteer'}
                            </button>
                        </li>
                    {/each}
                </ul>                <div class="mt-4 flex justify-between items-center gap-2">
                    <button
                        type="button"
                        on:click={handleClearOutputs}
                        class="text-sm text-red-600 hover:text-red-800 dark:text-red-500 dark:hover:text-red-400"
                    >
                        Wis Alle Opgeslagen Resultaten
                    </button>
                    {#if $subsidyStore.selectedOutput && $user?.role === 'admin'}
                        <button
                            type="button"
                            on:click={setAsGlobalStandard}
                            class="text-sm bg-purple-600 hover:bg-purple-700 text-white font-medium py-1 px-3 rounded focus:outline-none focus:shadow-outline flex items-center gap-2"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                            Maak Standaard voor alle Gebruikers
                        </button>
                    {:else}
                        <div></div>
                    {/if}
                </div>
            </div>
        {:else}
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5 flex items-center justify-center text-gray-500 dark:text-gray-400 min-h-[10rem]">
                <span>Nog geen resultaten opgeslagen.</span>
            </div>
        {/if}
    </div>

    {#if responseData || isLoading}
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
            {#if isLoading}
                <div class="flex justify-center items-center h-40">
                     <svg class="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                </div>
            {:else if responseData}
                <div class="space-y-4">
                    {#if !isEditMode}
                        <!-- Normal view mode -->
                        {#if responseData.summary}
                            <div class="border border-gray-300 rounded-md p-4 bg-gray-50 dark:bg-gray-700 dark:border-gray-600">
                                <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Samenvatting:</h3>
                                <p class="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{responseData.summary}</p>
                            </div>
                        {/if}
                        <div class="border border-gray-300 rounded-md p-4 bg-gray-50 dark:bg-gray-700 dark:border-gray-600">
                            <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">Geëxtraheerde Criteria:</h3>
                            {#if responseData.criteria && responseData.criteria.length > 0}
                                <ul class="list-disc list-inside space-y-2">
                                    {#each responseData.criteria as criterion (criterion.id)}
                                        <li class="text-gray-700 dark:text-gray-300">{criterion.text}</li>
                                    {/each}
                                </ul>
                            {:else}
                                <p class="text-gray-500 dark:text-gray-400">Geen criteria gevonden.</p>
                            {/if}
                        </div>
                        <div class="flex justify-between gap-2">
                            <button
                                type="button"
                                on:click={startEditMode}
                                class="bg-orange-600 hover:bg-orange-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline flex items-center gap-2"
                                title="Pas de criteria handmatig aan voordat u ze opslaat"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                Bewerk Criteria
                            </button>
                            <button
                                type="button"
                                on:click={saveCurrentOutput}
                                class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline flex items-center gap-2"
                                title="Voeg dit resultaat toe aan de lijst en geef een naam op"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" /></svg>
                                Sla Resultaat Op Met Naam...
                            </button>
                        </div>
                    {:else}
                        <!-- Edit mode -->
                        <div class="border border-orange-300 rounded-md p-4 bg-orange-50 dark:bg-orange-900/20 dark:border-orange-700">
                            <h3 class="text-lg font-semibold text-orange-800 dark:text-orange-200 mb-4 flex items-center gap-2">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                Bewerk Modus - Pas criteria aan
                            </h3>
                            
                            <!-- Editable summary -->
                            <div class="mb-4">
                                <label class="block text-sm font-medium text-orange-800 dark:text-orange-200 mb-2">
                                    Samenvatting:
                                </label>
                                <textarea
                                    bind:value={editableSummary}
                                    rows="3"
                                    class="w-full px-3 py-2 border border-orange-300 dark:border-orange-600 rounded-md shadow-sm bg-white dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-orange-500 focus:border-orange-500"
                                    placeholder="Voer een samenvatting in..."
                                />
                            </div>

                            <!-- Editable criteria -->
                            <div class="mb-4">
                                <div class="flex justify-between items-center mb-2">
                                    <label class="block text-sm font-medium text-orange-800 dark:text-orange-200">
                                        Criteria:
                                    </label>
                                    <button
                                        type="button"
                                        on:click={addCriterion}
                                        class="bg-green-600 hover:bg-green-700 text-white text-sm py-1 px-2 rounded focus:outline-none focus:shadow-outline flex items-center gap-1"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                                        </svg>
                                        Criterium toevoegen
                                    </button>
                                </div>
                                {#if editableCriteria.length > 0}
                                    <div class="space-y-3">
                                        {#each editableCriteria as criterion, index (criterion.id)}
                                            <div class="flex items-start gap-2 border border-gray-200 dark:border-gray-600 rounded p-3 bg-white dark:bg-gray-800">
                                                <span class="text-sm font-medium text-gray-600 dark:text-gray-400 mt-2 min-w-[2rem]">
                                                    {index + 1}.
                                                </span>
                                                <textarea
                                                    bind:value={criterion.text}
                                                    rows="2"
                                                    class="flex-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-orange-500 focus:border-orange-500"
                                                    placeholder="Voer criteriumtekst in..."
                                                />
                                                <button
                                                    type="button"
                                                    on:click={() => removeCriterion(index)}
                                                    class="bg-red-600 hover:bg-red-700 text-white text-sm py-1 px-2 rounded focus:outline-none focus:shadow-outline flex items-center"
                                                    title="Verwijder dit criterium"
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                    </svg>
                                                </button>
                                            </div>
                                        {/each}
                                    </div>
                                {:else}
                                    <p class="text-gray-500 dark:text-gray-400 text-center py-4">Geen criteria aanwezig. Klik op "Criterium toevoegen" om te beginnen.</p>
                                {/if}
                            </div>

                            <!-- Edit mode buttons -->
                            <div class="flex justify-between gap-2">
                                <button
                                    type="button"
                                    on:click={cancelEdit}
                                    class="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline flex items-center gap-2"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                    Annuleren
                                </button>
                                <button
                                    type="button"
                                    on:click={saveEditedCriteria}
                                    class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline flex items-center gap-2"
                                    title="Sla de aangepaste criteria op met een naam"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                                    </svg>
                                    Sla Aangepaste Versie Op
                                </button>
                            </div>
                        </div>
                    {/if}
                </div>
            {/if}
        </div>
    {/if}

    {#if $subsidyStore.selectedOutput}
        <div class="bg-blue-50 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700 rounded-lg shadow p-5">
            <h3 class="text-lg font-semibold text-blue-800 dark:text-blue-200 mb-2">Geselecteerd Resultaat: "{$subsidyStore.selectedOutput.name}"</h3>
            {#if $subsidyStore.selectedOutput.summary}
                <p class="text-sm text-blue-700 dark:text-blue-300 mb-2"><strong>Samenvatting:</strong> {$subsidyStore.selectedOutput.summary}</p>
            {/if}
            <p class="text-sm text-blue-700 dark:text-blue-300"><strong>Aantal criteria:</strong> {$subsidyStore.selectedOutput.criteria.length}</p>            <!-- Nieuwe knop om selectie op te slaan naar backend -->
            <div class="mt-4 flex justify-end">
                <button
                    type="button"
                    on:click={() => {
                        // Ga direct naar deel 2
                        window.location.href = '/app-launcher/subsidies2';
                    }}
                    class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline flex items-center gap-2 whitespace-nowrap"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                    </svg>
                    Ga naar beoordelingstool
                </button>
            </div>        </div>    {/if}
</div>

<!-- Info modal voor app uitleg -->
<Modal
  bind:show={showInfoModal}
  size="md"
  containerClassName="p-0"
>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
        Subsidie Criteria Tool - Handleiding
      </h3>
      <button
        type="button"
        on:click={() => showInfoModal = false}
        class="text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
      <div class="space-y-4 text-gray-700 dark:text-gray-300">
      <div>
        <h4 class="font-semibold text-gray-900 dark:text-white mb-2">🎯 Wat doet deze tool?</h4>
        <p class="text-sm">
          Deze <strong>Subsidie Criteria Extractor</strong> analyseert subsidiereglementen en haalt automatisch alle beoordelingscriteria eruit. 
          Het zorgt ervoor dat u niets vergeet bij het beoordelen van subsidieaanvragen en houdt u aan de regels.
        </p>
      </div>
      
      <div>
        <h4 class="font-semibold text-gray-900 dark:text-white mb-2">📋 Stap-voor-stap uitleg:</h4>
        <ol class="list-decimal list-inside text-sm space-y-2 pl-2">
          <li><strong>Input:</strong> Voer de volledige subsidieregeling in of upload een document (Word, PDF, TXT, RTF)</li>
          <li><strong>Analyse:</strong> De AI leest het document en haalt alle toetsingscriteria eruit</li>
          <li><strong>Opslaan:</strong> Geef het resultaat een duidelijke naam en sla het op</li>
          <li><strong>Selecteren:</strong> Kies de criteria die u wilt gebruiken en stel deze in als standaard voor alle gebruikers</li>
          <li><strong>Beoordelen:</strong> Ga naar de beoordelingstool om aanvragen systematisch te toetsen</li>
        </ol>
      </div>
        <div>
        <h4 class="font-semibold text-gray-900 dark:text-white mb-2">💡 Tips voor het beste resultaat:</h4>
        <ul class="list-disc list-inside text-sm space-y-1 pl-2">
          <li><strong>Volledigheid:</strong> Voer de complete regeling in, inclusief alle artikelen en bijlagen</li>
          <li><strong>Meerdere bestanden:</strong> Als een regeling uit meerdere documenten bestaat, plak deze dan samen in één bestand - het systeem kan slechts één bestand tegelijk verwerken</li>
          <li><strong>Bestandsformaten:</strong> Word (.doc, .docx), PDF, TXT of RTF bestanden worden ondersteund</li>
          <li><strong>Naamgeving:</strong> Gebruik duidelijke namen zoals "Evenementensubsidie 2024" of "Sportverenigingen regeling"</li>
        </ul>
      </div>
      
      <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
        <div class="flex items-start gap-3">
          <div class="text-blue-500 mt-0.5">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p class="text-sm font-medium text-blue-800 dark:text-blue-200 mb-1">
              Dit is Stap 1 van het beoordelingsproces
            </p>
            <p class="text-xs text-blue-700 dark:text-blue-300">
              Na het extraheren van criteria gaat u naar de beoordelingstool waar u daadwerkelijke subsidieaanvragen kunt toetsen aan deze criteria.
            </p>
          </div>
        </div>
      </div>
    </div>
    
    <div class="mt-6 flex justify-end">
      <button
        type="button"
        on:click={() => showInfoModal = false}
        class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded focus:outline-none focus:shadow-outline"
      >
        Begrepen
      </button>
    </div>
  </div>
</Modal>

<style>
  .progress-line {
    background-color: rgba(59, 130, 246, 0.1);
  }
  .progress-line .line {
    height: 100%;
    background-color: #3b82f6;
    animation: progress 2s infinite;
    width: 100%;
    transform-origin: left;
  }
  @keyframes progress {
    0% { transform: translateX(-100%); }
    50% { transform: translateX(0); }
    100% { transform: translateX(100%); }
  }

  @keyframes flash {
    0% { background-color: rgba(59, 130, 246, 0); box-shadow: 0 0 0 0 rgba(96, 165, 250, 0); }
    15% { background-color: rgba(59, 130, 246, 0.2); box-shadow: 0 0 30px 15px rgba(96, 165, 250, 0.3), 0 0 0 30px rgba(96, 165, 250, 0.1), inset 0 0 15px rgba(255, 255, 255, 0.4); }
    30% { background-color: rgba(59, 130, 246, 0.1); box-shadow: 0 0 50px 20px rgba(96, 165, 250, 0.1), 0 0 0 40px rgba(96, 165, 250, 0), inset 0 0 20px rgba(255, 255, 255, 0.2); }
    100% { background-color: rgba(59, 130, 246, 0); box-shadow: 0 0 0 0 rgba(96, 165, 250, 0); }
  }
  :global(.flash-animation) {
    animation: flash 1.0s cubic-bezier(0.4, 0, 0.2, 1);
    border-color: rgba(96, 165, 250, 0.8);
    position: relative;
  }
</style>