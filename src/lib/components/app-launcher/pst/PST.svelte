<script lang="ts">
  import { onMount } from 'svelte';
  import { WEBUI_BASE_URL } from '$lib/constants';
  import { toast } from 'svelte-sonner';
  import Modal from '$lib/components/common/Modal.svelte';
  import { fade } from 'svelte/transition';

  // State variables
  let isLoading = false;
  let uploadedFile: File | null = null;
  let pstData: any = null;
  let tempFilePath = '';
  let showAnalysisModal = false;
  let showSearchModal = false;
  let analysisResults: any = null;
  let searchResults: any = null;
  let searchQuery = '';
  let searchCriteria = ['subject', 'sender', 'body'];
  let maxMessages = 1000;
  let includeBody = false;
  let folderFilter = '';
  let selectedFolder = '';
  let dateFrom = '';
  let dateTo = '';
  let isAnalyzing = false;
  let isSearching = false;
  let requirements: any = null;
  let selectedFolders: string[] = [];
  let showFolderSelection = false;

  onMount(async () => {
    await checkRequirements();
  });

  async function checkRequirements() {
    try {
      const response = await fetch(`${WEBUI_BASE_URL}/api/pst/requirements`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        requirements = await response.json();
      }
    } catch (error) {
      console.error('Error checking requirements:', error);
    }
  }

  async function handleFileUpload(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pst') && !file.name.toLowerCase().endsWith('.ost')) {
      toast.error('Alleen PST en OST bestanden zijn toegestaan');
      return;
    }

    uploadedFile = file;
    isLoading = true;

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${WEBUI_BASE_URL}/api/pst/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      pstData = data;
      tempFilePath = data.temp_file_path;
      
      toast.success('PST bestand succesvol geüpload en geparset');
    } catch (error: any) {
      console.error('Upload error:', error);
      toast.error(`Upload fout: ${error.message}`);
    } finally {
      isLoading = false;
    }
  }

  async function startAnalysis() {
    if (!tempFilePath) {
      toast.error('Geen PST bestand geüpload');
      return;
    }

    isAnalyzing = true;
    
    try {
      const requestBody = {
        file_path: tempFilePath,
        include_body: includeBody,
        max_messages: maxMessages > 0 ? maxMessages : null,
        folder_filter: folderFilter || null,
        selected_folders: selectedFolders.length > 0 ? selectedFolders : null
      };

      const response = await fetch(`${WEBUI_BASE_URL}/api/pst/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Analysis failed');
      }

      analysisResults = await response.json();
      showAnalysisModal = true;
      
    } catch (error: any) {
      console.error('Analysis error:', error);
      toast.error(`Analyse fout: ${error.message}`);
    } finally {
      isAnalyzing = false;
    }
  }

  async function startSearch() {
    if (!tempFilePath || !searchQuery.trim()) {
      toast.error('Voer een zoekterm in');
      return;
    }

    isSearching = true;
    
    try {
      const requestBody = {
        file_path: tempFilePath,
        query: searchQuery,
        search_in: searchCriteria,
        date_from: dateFrom || null,
        date_to: dateTo || null,
        folder_path: selectedFolder || null,
        selected_folders: selectedFolders.length > 0 ? selectedFolders : null
      };

      const response = await fetch(`${WEBUI_BASE_URL}/api/pst/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Search failed');
      }

      searchResults = await response.json();
      showSearchModal = true;
      
    } catch (error: any) {
      console.error('Search error:', error);
      toast.error(`Zoek fout: ${error.message}`);
    } finally {
      isSearching = false;
    }
  }

  async function cleanup() {
    if (!tempFilePath) return;
    
    try {
      const response = await fetch(`${WEBUI_BASE_URL}/api/pst/cleanup/${encodeURIComponent(tempFilePath)}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        pstData = null;
        tempFilePath = '';
        uploadedFile = null;
        analysisResults = null;
        searchResults = null;
        toast.success('Temporary files cleaned up');
      }
    } catch (error) {
      console.error('Cleanup error:', error);
    }
  }

  function formatDate(dateString: string) {
    if (!dateString) return 'Onbekend';
    return new Date(dateString).toLocaleString('nl-NL');
  }

  function formatFileSize(bytes: number) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  function renderFolderStructure(folders: any[], depth = 0): any[] {
    return folders.map(folder => ({
      ...folder,
      depth,
      children: folder.sub_folders ? renderFolderStructure(folder.sub_folders, depth + 1) : []
    })).flat();
  }

  function toggleFolderSelection(folderPath: string) {
    if (selectedFolders.includes(folderPath)) {
      selectedFolders = selectedFolders.filter(path => path !== folderPath);
    } else {
      selectedFolders = [...selectedFolders, folderPath];
    }
  }

  function selectAllFolders() {
    selectedFolders = flattenedFolders.map(folder => folder.path);
  }

  function clearFolderSelection() {
    selectedFolders = [];
  }

  $: flattenedFolders = pstData?.folders ? renderFolderStructure(pstData.folders) : [];
</script>

<div class="max-w-7xl mx-auto mt-6">
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-800 dark:text-white">
        PST/OST Bestand Analyzer
      </h1>
      
      {#if pstData}
        <button
          on:click={cleanup}
          class="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-md"
        >
          Opruimen
        </button>
      {/if}
    </div>

    <!-- Requirements Check -->
    {#if requirements && !requirements.all_satisfied}
      <div class="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-6" transition:fade>
        <h3 class="font-bold">Vereisten niet voldaan</h3>
        <p class="mt-2">De volgende bibliotheken zijn vereist voor PST parsing:</p>
        <ul class="mt-2 list-disc list-inside">
          {#each Object.entries(requirements.requirements) as [name, req]}
            {#if !req.installed}
              <li>
                <strong>{name}</strong>: {req.description}
                <br>
                <code class="bg-gray-200 dark:bg-gray-700 px-2 py-1 rounded text-sm">{req.install_command}</code>
              </li>
            {/if}
          {/each}
        </ul>
      </div>
    {/if}

    <!-- File Upload Section -->
    <div class="mb-6">
      <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        PST/OST Bestand Uploaden
      </label>
      
      <div class="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
        <input
          type="file"
          accept=".pst,.ost"
          on:change={handleFileUpload}
          class="hidden"
          id="pst-upload"
          disabled={isLoading}
        />
        
        <label for="pst-upload" class="cursor-pointer">
          {#if isLoading}
            <div class="flex items-center justify-center">
              <svg class="animate-spin h-8 w-8 text-blue-600 mr-2" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span class="text-gray-600 dark:text-gray-400">Bestand uploaden en parsen...</span>
            </div>
          {:else}
            <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <p class="mt-2 text-gray-600 dark:text-gray-400">
              <span class="font-medium text-blue-600 hover:text-blue-500">Klik om een bestand te selecteren</span>
              of sleep het hierheen
            </p>
            <p class="text-xs text-gray-500">PST en OST bestanden tot 500MB</p>
          {/if}
        </label>
      </div>

      {#if uploadedFile}
        <div class="mt-4 text-sm text-gray-600 dark:text-gray-400">
          Geüpload: <strong>{uploadedFile.name}</strong> ({formatFileSize(uploadedFile.size)})
        </div>
      {/if}
    </div>

    <!-- PST Information Display -->
    {#if pstData}
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6" transition:fade>
        <!-- File Information -->
        <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-800 dark:text-white mb-3">Bestand Informatie</h3>
          <dl class="space-y-2">
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600 dark:text-gray-400">Bestandsnaam:</dt>
              <dd class="text-sm font-medium text-gray-900 dark:text-white">{pstData.file_info.filename}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600 dark:text-gray-400">Grootte:</dt>
              <dd class="text-sm font-medium text-gray-900 dark:text-white">{formatFileSize(pstData.file_info.size)}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600 dark:text-gray-400">Mappen:</dt>
              <dd class="text-sm font-medium text-gray-900 dark:text-white">{pstData.file_info.folder_count}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600 dark:text-gray-400">Berichten:</dt>
              <dd class="text-sm font-medium text-gray-900 dark:text-white">{pstData.file_info.message_count}</dd>
            </div>
          </dl>
        </div>

        <!-- Action Buttons -->
        <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-800 dark:text-white mb-3">Acties</h3>
          <div class="space-y-3">
            <button
              on:click={() => showAnalysisModal = true}
              disabled={isAnalyzing}
              class="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-md flex items-center justify-center"
            >
              {#if isAnalyzing}
                <svg class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Analyseren...
              {:else}
                Analyseer Berichten
                {#if selectedFolders.length > 0}
                  <span class="text-xs bg-blue-500 text-white px-2 py-1 rounded-full ml-2">
                    {selectedFolders.length} mappen
                  </span>
                {/if}
              {/if}
            </button>
            
            <button
              on:click={() => showSearchModal = true}
              disabled={isSearching}
              class="w-full bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-md flex items-center justify-center"
            >
              {#if isSearching}
                <svg class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Zoeken...
              {:else}
                Zoek in Berichten
                {#if selectedFolders.length > 0}
                  <span class="text-xs bg-green-500 text-white px-2 py-1 rounded-full ml-2">
                    {selectedFolders.length} mappen
                  </span>
                {/if}
              {/if}
            </button>
          </div>
        </div>
      </div>

      <!-- Folder Structure -->
      <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-lg font-medium text-gray-800 dark:text-white">Mappenstructuur</h3>
          <button
            on:click={() => showFolderSelection = !showFolderSelection}
            class="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded-md"
          >
            {showFolderSelection ? 'Verberg Selectie' : 'Selecteer Mappen'}
          </button>
        </div>
        
        {#if showFolderSelection}
          <div class="mb-4 p-4 bg-blue-50 dark:bg-blue-900 rounded-lg" transition:fade>
            <div class="flex justify-between items-center mb-2">
              <span class="text-sm font-medium text-blue-800 dark:text-blue-200">
                Map Selectie ({selectedFolders.length} geselecteerd)
              </span>
              <div class="space-x-2">
                <button
                  on:click={selectAllFolders}
                  class="text-xs bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded"
                >
                  Alles
                </button>
                <button
                  on:click={clearFolderSelection}
                  class="text-xs bg-gray-600 hover:bg-gray-700 text-white px-2 py-1 rounded"
                >
                  Wissen
                </button>
              </div>
            </div>
            <p class="text-xs text-blue-700 dark:text-blue-300 mb-3">
              Selecteer de mappen die je wilt analyseren of doorzoeken. Als geen mappen geselecteerd zijn, worden alle mappen gebruikt.
            </p>
          </div>
        {/if}
        
        <div class="max-h-64 overflow-y-auto">
          {#each flattenedFolders as folder}
            <div class="flex items-center py-1" style="margin-left: {folder.depth * 20}px;">
              {#if showFolderSelection}
                <input
                  type="checkbox"
                  checked={selectedFolders.includes(folder.path)}
                  on:change={() => toggleFolderSelection(folder.path)}
                  class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded mr-2"
                />
              {/if}
              <svg class="h-4 w-4 text-gray-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"></path>
              </svg>
              <span class="text-sm text-gray-700 dark:text-gray-300">{folder.name}</span>
              <span class="text-xs text-gray-500 ml-2">({folder.message_count} berichten)</span>
              {#if selectedFolders.includes(folder.path)}
                <svg class="h-4 w-4 text-blue-500 ml-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                </svg>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<!-- Analysis Modal -->
<Modal bind:show={showAnalysisModal} size="lg">
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-bold text-gray-800 dark:text-white">Analyse Configuratie</h2>
      <button
        on:click={() => showAnalysisModal = false}
        class="text-gray-400 hover:text-gray-500"
      >
        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <div class="space-y-4">
      {#if selectedFolders.length > 0}
        <div class="bg-blue-50 dark:bg-blue-900 rounded-lg p-4">
          <h4 class="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
            Geselecteerde mappen ({selectedFolders.length})
          </h4>
          <div class="max-h-32 overflow-y-auto">
            {#each selectedFolders as folderPath}
              <div class="text-xs text-blue-700 dark:text-blue-300 py-1">
                {folderPath}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Maximum aantal berichten
        </label>
        <input
          type="number"
          bind:value={maxMessages}
          min="1"
          max="10000"
          class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Map filter (optioneel)
        </label>
        <input
          type="text"
          bind:value={folderFilter}
          placeholder="bijv. Inbox, Sent Items"
          class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
      </div>

      <div class="flex items-center">
        <input
          type="checkbox"
          bind:checked={includeBody}
          id="include-body"
          class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
        />
        <label for="include-body" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
          Bericht inhoud meenemen (langzamer)
        </label>
      </div>
    </div>

    <div class="mt-6 flex justify-end space-x-3">
      <button
        on:click={() => showAnalysisModal = false}
        class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
      >
        Annuleren
      </button>
      <button
        on:click={() => { showAnalysisModal = false; startAnalysis(); }}
        disabled={isAnalyzing}
        class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-md"
      >
        Start Analyse
      </button>
    </div>
  </div>
</Modal>

<!-- Search Modal -->
<Modal bind:show={showSearchModal} size="lg">
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-bold text-gray-800 dark:text-white">Zoek Configuratie</h2>
      <button
        on:click={() => showSearchModal = false}
        class="text-gray-400 hover:text-gray-500"
      >
        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <div class="space-y-4">
      {#if selectedFolders.length > 0}
        <div class="bg-green-50 dark:bg-green-900 rounded-lg p-4">
          <h4 class="text-sm font-medium text-green-800 dark:text-green-200 mb-2">
            Zoeken in geselecteerde mappen ({selectedFolders.length})
          </h4>
          <div class="max-h-32 overflow-y-auto">
            {#each selectedFolders as folderPath}
              <div class="text-xs text-green-700 dark:text-green-300 py-1">
                {folderPath}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Zoekterm
        </label>
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Voer zoekterm in..."
          class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Zoek in:
        </label>
        <div class="space-y-2">
          {#each [['subject', 'Onderwerp'], ['sender', 'Afzender'], ['body', 'Bericht inhoud'], ['recipients', 'Ontvangers']] as [value, label]}
            <div class="flex items-center">
              <input
                type="checkbox"
                bind:group={searchCriteria}
                {value}
                id="search-{value}"
                class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label for="search-{value}" class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                {label}
              </label>
            </div>
          {/each}
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Van datum
          </label>
          <input
            type="date"
            bind:value={dateFrom}
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Tot datum
          </label>
          <input
            type="date"
            bind:value={dateTo}
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          />
        </div>
      </div>
    </div>

    <div class="mt-6 flex justify-end space-x-3">
      <button
        on:click={() => showSearchModal = false}
        class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
      >
        Annuleren
      </button>
      <button
        on:click={() => { showSearchModal = false; startSearch(); }}
        disabled={isSearching || !searchQuery.trim()}
        class="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded-md"
      >
        Zoeken
      </button>
    </div>
  </div>
</Modal>

<!-- Results Display -->
{#if analysisResults}
  <div class="max-w-7xl mx-auto mt-6">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6" transition:fade>
      <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-4">Analyse Resultaten</h2>
      
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div class="bg-blue-50 dark:bg-blue-900 rounded-lg p-4">
          <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">{analysisResults.summary.total_messages}</div>
          <div class="text-sm text-blue-600 dark:text-blue-400">Totaal berichten</div>
        </div>
        <div class="bg-green-50 dark:bg-green-900 rounded-lg p-4">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400">{analysisResults.summary.total_attachments}</div>
          <div class="text-sm text-green-600 dark:text-green-400">Bijlagen</div>
        </div>
        <div class="bg-purple-50 dark:bg-purple-900 rounded-lg p-4">
          <div class="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {analysisResults.summary.date_range.earliest ? 
              new Date(analysisResults.summary.date_range.earliest).getFullYear() + '-' + 
              new Date(analysisResults.summary.date_range.latest).getFullYear() : 'N/A'}
          </div>
          <div class="text-sm text-purple-600 dark:text-purple-400">Datum bereik</div>
        </div>
      </div>

      <div class="max-h-96 overflow-y-auto">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead class="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Onderwerp</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Afzender</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Datum</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Map</th>
            </tr>
          </thead>
          <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {#each analysisResults.messages.slice(0, 100) as message}
              <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                  {message.subject || '(Geen onderwerp)'}
                  {#if message.has_attachments}
                    <svg class="inline h-4 w-4 text-gray-400 ml-1" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" clip-rule="evenodd" />
                    </svg>
                  {/if}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{message.sender || 'Onbekend'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{formatDate(message.sent_time)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300">{message.folder_path}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  </div>
{/if}

{#if searchResults}
  <div class="max-w-7xl mx-auto mt-6">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6" transition:fade>
      <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-4">Zoek Resultaten</h2>
      
      <div class="mb-4">
        <p class="text-sm text-gray-600 dark:text-gray-400">
          {searchResults.results_count} resultaten gevonden voor "{searchResults.query}"
        </p>
      </div>

      <div class="max-h-96 overflow-y-auto">
        {#each searchResults.results as result}
          <div class="border-b border-gray-200 dark:border-gray-700 py-4">
            <div class="flex justify-between items-start">
              <div>
                <h3 class="text-sm font-medium text-gray-900 dark:text-white">
                  {result.subject || '(Geen onderwerp)'}
                  {#if result.has_attachments}
                    <svg class="inline h-4 w-4 text-gray-400 ml-1" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" clip-rule="evenodd" />
                    </svg>
                  {/if}
                </h3>
                <p class="text-sm text-gray-500 dark:text-gray-400">Van: {result.sender}</p>
                <p class="text-xs text-gray-400">Map: {result.folder_path}</p>
                <div class="mt-2">
                  {#each result.match_details as detail}
                    <span class="inline-block bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded mr-1">
                      {detail}
                    </span>
                  {/each}
                </div>
              </div>
              <div class="text-xs text-gray-400">
                {formatDate(result.sent_time)}
              </div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>
{/if}
