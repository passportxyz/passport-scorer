import { writable } from 'svelte/store';

export const address = writable(null as string|null);
