# Community references and outreach

Research checked on **2026-10-02** using the linked project documentation and
GitHub contribution rules. The proposals below are prepared locally; no upstream
pull request, discussion or message has been sent by preparing this page.

## Where NiriFX fits

| Priority | Venue | Useful contribution and current status |
| --- | --- | --- |
| 1 | [awesome-niri / Custom Shaders](https://github.com/niri-wm/awesome-niri#custom-shaders) | Best direct listing fit. Its guidelines accept niri-specific projects. One alphabetized entry and PR text are [prepared](awesome-niri-submission.md). No matching open/closed PR found in the research check. |
| 2 | [niri / Show and tell](https://github.com/niri-wm/niri/discussions/categories/show-and-tell) | Appropriate channel for one short introduction, a real open/close GIF, setup link and explicit experimental-movement limits. [Draft below](#showcase-draft). |
| 3 | [Noctalia Niri Animations](https://github.com/noctalia-dev/community-plugins/tree/main/niri-animations) | The README already describes third-party KDL collections. A [preset-folder documentation patch](noctalia-preset-folder.patch) explains concrete settings. Validate in Noctalia before submitting; the existing plugin's maintainer reviews changes to their plugin. |
| 4 | [iNiR](https://github.com/snowarch/iNiR) | A tested external-preset example or Studio-launcher integration could help users. Contributions target `prerelease`, with the exact flow exercised on a real iNiR setup. Start with a small integration proposal, not a request for a promotional banner. |
| Later | [DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell) | Validate a DMS session and provide a useful settings/launcher integration before requesting a native plugin listing. Current support is niri KDL only. |
| Reference | [niri-animation-collection](https://github.com/jgarza9788/niri-animation-collection) | Accepts concrete animation contributions using its template and GIF workflow. A self-contained shader contribution may fit; a bare advertisement does not follow that contribution path. |

Guidelines: [awesome-niri](https://github.com/niri-wm/awesome-niri/blob/main/CONTRIBUTING.md),
[Noctalia community plugins](https://github.com/noctalia-dev/community-plugins),
[iNiR](https://github.com/snowarch/iNiR/blob/main/CONTRIBUTING.md),
[DMS](https://github.com/AvengeMedia/DankMaterialShell/blob/master/CONTRIBUTING.md).

Quickshell's project showcase is for things built with its toolkit. NiriFX is a
Python/WebGL application, so “Built with Quickshell” would be inaccurate. Link
Quickshell as part of the surrounding shell ecosystem instead. Likewise,
Burn-My-Windows and Compiz are related effects projects, not implied sponsors or
places to open promotion-only bug reports.

## Submission practice

Disclose that you maintain the project, link one relevant demo and installation
instructions, and state tested support plainly. Search existing issues/PRs and
refresh the target's guidelines before sending. Keep an upstream change focused
and accept a maintainer's decision without repeated requests or cross-post spam.
No automatic posting, mass mentions, reciprocal-star requests or unsolicited
messages are needed. New public submissions require the project owner's approval.

## Showcase draft

**NiriFX: fragments, slices and springy window animations for niri**

I maintain [NiriFX](https://github.com/jturbide/niri-fx), a small window-effects
studio for niri. It offers configurable textured fragments, sliding strips and
elastic open/close effects, with a local visual editor and KDL export.

[Recorded examples](https://github.com/jturbide/niri-fx#see-it-in-motion) ·
[Getting started](https://github.com/jturbide/niri-fx/blob/main/docs/getting-started.md)

The ordinary effects use stock niri shaders. Resize remains opt-in. Native
move/swap effects are a separate compositor experiment, and the Studio concepts
are labelled separately from native recordings. iNiR/iRiS has a preset adapter;
Noctalia consumes an exported KDL folder; its 5.2.1 picker passed isolated profile
selection and return to base. DMS also has an optional launcher adapter.

Feedback on visual quality and GPU behavior with synthetic examples would help.
This is an independent early project, not an official niri or shell component.
