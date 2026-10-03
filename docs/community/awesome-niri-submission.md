# Proposed awesome-niri listing

Target: [niri-wm/awesome-niri](https://github.com/niri-wm/awesome-niri), `main`,
**Custom Shaders**. This is a prepared submission, not a posted pull request.

Title: **Add NiriFX window effects studio**

Proposed entry:

> - [NiriFX](https://github.com/jturbide/niri-fx) - Configurable fragment, slice and elastic window shaders for niri, with a visual editor.

Pull request body:

I maintain NiriFX and would like to suggest it for Custom Shaders. It provides
configurable fragment, slice and elastic open/close shaders for stock niri, a
local visual editor, CLI exports and optional shell integrations. Its README
includes recorded examples and explicit support limits. Native movement is a
separate experimental compositor build; the ordinary effects do not require it.

This adds one alphabetized entry. I checked existing entries and searched open
and closed pull requests for NiriFX, niri-fx and niri-fragments without finding a
duplicate on 2026-10-02. The implementation uses Python, GLSL and WebGL and is
MIT-licensed; the optional Niri-derived compositor patch has its separate GPL license.

[Prepared patch](awesome-niri.patch). Before sending, refresh upstream and repeat
the duplicate search. Follow [their guidelines](https://github.com/niri-wm/awesome-niri/blob/main/CONTRIBUTING.md)
and run `awesome-lint`; disclose unrelated pre-existing lint findings rather than
reformatting the list. Only the project owner should authorize publication.

Validation: `awesome-lint@2.3.0` passes on upstream and the proposed entry.
The contribution guide requests an em dash, but the required linter rejects it;
the patch uses the ASCII hyphen already used by this section to satisfy the check.
