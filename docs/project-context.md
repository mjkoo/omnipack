# Project context

The project is named **omnipack**, previously obtainium-emulation-pack.
Its canonical repository identifier is `mjkoo/omnipack`. The Python
distribution and import package are `omnipack`; development commands retain
the `pack` entry point.

The original goal is a single-file Obtainium import for each of single-screen
and dual-screen devices, combining upstream catalogs with personal additions.
Version-detection fixes must survive upstream refreshes: manual edits in
Obtainium previously caused maintenance work and recurring update prompts.
Declare those fixes in the committed overlay as they are identified.
Consumers fetch JSON from main; release packaging is not required.

The original curation request also called for the owner's fork of
`isledecomp/isle-portable`. Its repository URL was not supplied. This remains
a pending request, not an instruction to add the upstream project or guess a
fork URL. Cinderbox, the other explicit addition, is already configured.

`RJNY/Obtainium-Emulation-Pack` is an independent upstream and retains its
name in source configuration, app provenance, fixtures, and attribution.
Its own pack tracker is excluded from both exports; RJNY remains an app source.
The legacy nightly issue ownership marker also remains stable so automation
can recognize existing issues. Archived planning artifacts retain their
historical names.
