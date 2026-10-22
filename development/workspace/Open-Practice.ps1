$ErrorActionPreference='Stop'
# A real shuffled match using the verified private sandbox card set.
& (Join-Path $PSScriptRoot 'Open-Playable.ps1') -DeckPath (Join-Path $PSScriptRoot 'decks\White-Blue-Study.txt') -OpponentDeckPath (Join-Path $PSScriptRoot 'decks\White-Blue-Tempo.txt')
