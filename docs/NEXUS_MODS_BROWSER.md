# Nexus Mods browser

The Editing and Research menu opens a read-only browser for confirmed Nexus game
domains associated with supported Windows PC profiles. It uses the documented
Nexus Mods v3 API over HTTPS. The API's current mod search, detail, file, version
and dependency endpoints are marked **Experimental**, so the integration is
isolated in `koei_editor.mods.nexus_api` and should be rechecked against the
current OpenAPI document when Nexus changes its schema.

## Supported game domains

Domains are explicit; the browser does not derive them from display names. Each
game page below was checked on the official Nexus site.

| Supported PC profile | Nexus domain | Official page |
| --- | --- | --- |
| Dynasty Warriors 8 XL | `dynastywarriors8` | [Nexus game page](https://www.nexusmods.com/games/dynastywarriors8) |
| Pirate Warriors 3 | `onepiecepiratewarriors3` | [Nexus game page](https://www.nexusmods.com/games/onepiecepiratewarriors3) |
| Pirate Warriors 4 | `onepiecepiratewarriors4` | [Nexus game page](https://www.nexusmods.com/games/onepiecepiratewarriors4) |
| Atelier Sophie 2 | `ateliersophie2` | [Nexus game page](https://www.nexusmods.com/games/ateliersophie2) |
| Dynasty Warriors: Origins | `dynastywarriorsorigins` | [Nexus game page](https://www.nexusmods.com/games/dynastywarriorsorigins) |
| Samurai Warriors 4-II | `samuraiwarriors4ii` | [Nexus game page](https://www.nexusmods.com/games/samuraiwarriors4ii) |
| Samurai Warriors 2 | `samuraiwarriors2` | [Nexus game page](https://www.nexusmods.com/games/samuraiwarriors2) |
| Dynasty Warriors 6 | `dynastywarriors6` | [Nexus game page](https://www.nexusmods.com/games/dynastywarriors6) |
| Warriors All-Stars | `warriorsallstars` | [Nexus game page](https://www.nexusmods.com/games/warriorsallstars) |
| Warriors Orochi 3 Ultimate | `warriorsorochi3` | [Nexus game page](https://www.nexusmods.com/games/warriorsorochi3) |
| Wo Long: Fallen Dynasty | `wolongfallendynasty` | [Nexus game page](https://www.nexusmods.com/games/wolongfallendynasty) |
| Persona 5 Strikers | `persona5strikers` | [Nexus game page](https://www.nexusmods.com/games/persona5strikers) |
| Nioh 3 | `nioh3` | [Nexus game page](https://www.nexusmods.com/games/nioh3) |
| Dragon Quest Builders 2 | `dragonquestbuilders2` | [Nexus game page](https://www.nexusmods.com/games/dragonquestbuilders2) |
| Warriors Orochi 4 and 4 Ultimate | `warriorsorochi4` | [Nexus game page](https://www.nexusmods.com/games/warriorsorochi4) |
| Samurai Warriors 5 | `samuraiwarriors5` | [Nexus game page](https://www.nexusmods.com/games/samuraiwarriors5) |
| Warriors: Abyss | `warriorsabyss` | [Nexus game page](https://www.nexusmods.com/games/warriorsabyss) |
| Blue Reflection: Second Light | `bluereflectionsecondlight` | [Nexus game page](https://www.nexusmods.com/games/bluereflectionsecondlight) |

The Atelier Ryza 3 DX profile is not mapped to the `atelierryza3` Nexus page:
that page is for the original Ryza 3, and exact DX compatibility was not
confirmed. Other supported profiles without a confirmed game domain are omitted
until their page is verified.

## Discovery and metadata

The browser uses the endpoints described in the [official API reference](https://api-docs.nexusmods.com/)
and [OpenAPI schema](https://api.nexusmods.com/openapi.yaml):

| Purpose | API operation |
| --- | --- |
| Mod discovery | `POST /v3/mods/search` |
| Mod details and description | `GET /v3/games/{game_domain}/mods/{game_scoped_id}` |
| Mod files | `GET /v3/mods/{mod_id}/files` |
| Versions for one mod file | `GET /v3/mod-files/{file_id}/versions` |
| Declared file-version dependencies | `GET /v3/mod-file-versions/{version_id}/dependencies` |

Nexus's search request has filters for games and time range, sort modes, and
pagination, but no text-query field. The UI fetches one 30-item page at a time
and filters already loaded names, summaries, versions and authors locally. It
does not fetch every page in the background. A search result's description is
loaded only after the user selects that mod and supplies an API key.

Adult entries are excluded in the request and again in the client. Mod
descriptions arrive as uploader-authored BBCode; the browser displays plain text
and does not render remote HTML, images or clickable description markup. The
separate **Open Nexus page** action opens the official mod page when requested.

The dependency endpoint returns authored dependency definitions. Ranges within
one definition are alternatives; separate definitions are independent
requirements. The browser preserves that grouping in its display. It does not
install or resolve dependencies.

## Authentication, use limits and privacy

Mod search permits anonymous API requests. Details, files, versions and
dependencies require the user's Nexus API key. The key can be entered in the
browser and is held in memory only for that application session. It is sent in
the `apikey` request header to `https://api.nexusmods.com`; it is not saved in
preferences, placed in URLs, or included in error text. Search and metadata are
loaded only after a user action and kept in memory for the open session.

The client sends the required stable `Application-Name` and current
`Application-Version` headers, captures Nexus rate-limit response headers,
does not retry automatically, and surfaces HTTP 429 responses. Users should
wait for Nexus's reset or `Retry-After` before trying again. The current
[rate-limit help page](https://help.nexusmods.com/article/105-i-have-reached-a-daily-or-hourly-limit-api-requests-have-been-consumed-rate-limit-exceeded-what-does-this-mean)
documents the daily and hourly quotas; this client does not hard-code a quota.

The [Nexus API Acceptable Use Policy](https://help.nexusmods.com/article/114-api-acceptable-use-policy)
limits API-key use and prohibits bulk fetching data for rehosting. Personal API
keys are for personal use or development testing. Nexus requires a public-facing
application to contact its support team with a testing build before registration
and wider deployment. This code change does not register an application, request
an API key, or authorize a public release. Follow Nexus's current policy before
distributing an API-enabled build.

## Mod Manager handoff

There is no Mod Manager component or published handoff interface in this
repository yet. The browser exposes the typed
`NexusDownloadRequest`/`DownloadHandoff` boundary. The **Send to Mod Manager**
button stays disabled until a manager implementation is attached through
`Application.set_mod_manager_download_handoff(...)`. The manager receives only the
provider, game domain, game-scoped mod ID, mod ID, file ID, version IDs and
official mod-page URL. It does not receive the browser's API key or a signed CDN
URL.

The browser deliberately does not call Nexus's download-link endpoint, fetch
archive bytes, choose install paths, resolve dependencies, or install files. The
manager owns those operations and must follow Nexus's current eligibility rules:
some files require the key and expiry values produced by a user-initiated
download flow; quarantined files and moderated mods are not downloadable. Signed
links expire and should not be persisted. The current [OpenAPI download-link
description](https://api-docs.nexusmods.com/) records the exact rules. A future
Mod Manager PR can attach a fast `enqueue_nexus_download(request) -> bool`
capability and keep its download/install implementation in its own module.

## Automated checks

`tests/test_nexus_mods.py` uses only mocked HTTP responses. It covers the
documented request shape, local filtering, plain-text descriptions, required
authentication, rate and permission errors, response parsing, explicit game
domains, and the ID-only handoff. It never contacts Nexus or handles mod archives.
`tests/test_nexus_contract_audit.py` checks that only rate-limit telemetry
headers are retained, and the workspace test guards against handing off a stale
file version while another file is loading.
The application-shell test verifies navigation, localization and that the
manager action stays disabled without an attached manager.
