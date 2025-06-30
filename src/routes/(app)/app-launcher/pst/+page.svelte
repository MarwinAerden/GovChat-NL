<script lang="ts">
	import PST from '$lib/components/app-launcher/pst/PST.svelte';
	import Lechat from '$lib/components/chat/lechat.svelte';
	import { onMount, onDestroy } from 'svelte';
	import { currentAppContext } from '$lib/stores/appModels';

	onMount(() => {
		// Set app context for Subsidie app
		currentAppContext.set('subsidie');
	});

	onDestroy(() => {
		// Reset app context when leaving Subsidie app
		currentAppContext.set('general');
	});
</script>
  
  <!-- Content Slot -->
  <Lechat>
	<div slot="content" class="pt-6">
	  <PST />
	</div>
  </Lechat>