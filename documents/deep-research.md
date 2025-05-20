> This was written by ChatGPT deep research as a quick way to explore ideas.

# Architecture Design for `hass-immich-addon`

## Overview and Objectives

The `hass-immich-addon` is a Home Assistant add-on that generates a **daily photo slideshow** from an Immich photo server. It runs as a Dockerized service and periodically selects images (daily by default) to display on Home Assistant dashboards. The design emphasizes **modularity** and **separation of concerns**, meaning each part of the system (prompt generation, image search, download, integration) is handled by a dedicated module for clarity and maintainability. Key objectives include:

* **Automated Prompt Generation:** Create or fetch a descriptive prompt each day from various sources (static lists, files, LLMs, etc.).
* **Intelligent Image Selection:** Use the prompt (or other modes like random or “On This Day”) to query Immich for relevant images.
* **Efficient Asset Retrieval:** Download a set of 5–10 images (thumbnails or low-res) and cache them in Home Assistant’s `www` directory for easy access.
* **Home Assistant Integration:** Expose the images to Lovelace UI (e.g. via Gallery or Picture cards) and optionally make the current prompt visible (e.g. via an `input_text` entity or a markdown display).
* **User Configuration:** Allow flexible setup via a config file (YAML/JSON), including Immich connection, prompt source preferences, image selection mode, number of images, and update schedule (cron syntax).
* **Containerization & Maintainability:** Package the solution as a clean Python project with multiple modules, a lightweight Docker image, and CI/CD pipeline for building and publishing updates.

## 1. Prompt Generation Module

Each day (or on the defined schedule), the add-on must obtain a **prompt** that describes what images to show. The architecture supports multiple prompt sources through a unified interface (e.g. a `PromptGenerator` class with interchangeable strategies). Possible prompt sources include:

* **Static List:** A predefined list of prompts in the config. The add-on can cycle through them or pick the next one each day. (For example, a list of themes like “sunset scenes”, “family portraits”, “vacation photos”, etc.)
* **Random From File:** The add-on can read a text file containing many prompt lines and pick one at random. This allows easy customization – users can maintain a file of prompts and the system will surprise them daily with one.
* **Home Assistant Input Text:** Use the content of a Home Assistant `input_text` entity as the prompt. This allows the user to manually set or automate the prompt via Home Assistant UI/automations. The add-on would call Home Assistant’s API to read the value of a specified `input_text` entity at runtime.
* **Local LLM (Ollama):** Query a local Large Language Model (like an instance of Ollama or another local AI) to dynamically generate a prompt. For example, the add-on could send a request to a local Ollama API with a context (like date or events) and get back a creative prompt (e.g. *“A nostalgic family moment from past holidays”*).
* **OpenAI API (ChatGPT):** Use an OpenAI API (with a provided API key) to generate a prompt. The add-on could send a brief to ChatGPT (e.g. “Give me a photo theme for today’s slideshow”) and use the response text as the prompt. This could incorporate contextual info like date or notable events.
* **Calendar-based Prompt (Optional):** If enabled, the module can integrate calendar data (Home Assistant calendars or external iCal feeds) to influence the prompt. For instance, if today is a holiday or a family birthday (detected from a calendar), the prompt generator might produce a theme related to that event (e.g. *“Today is John’s birthday – show memorable moments with John”*).

All these strategies are implemented as separate classes or functions in a `prompt_sources` package. The add-on configuration lets the user choose a **primary prompt source** (and provide any needed details like file path or API keys). The `PromptGeneration` module will then:

* At each scheduled run, invoke the selected prompt source to get the day’s prompt (string).
* Log or store the prompt for reference.
* Fall back gracefully if one method fails (e.g., if the OpenAI API call fails, it could fall back to a default prompt or a random one, to ensure the slideshow still updates).

By abstracting this logic, adding new prompt sources in the future is straightforward (just add a new class implementing the interface).

## 2. Image Selection Module

Once a prompt is obtained, the Image Selection module decides which images from Immich to use. This module interacts with Immich’s API to fetch relevant image IDs based on the configured **mode**:

* **Prompt-Based Search (CLIP):** If the mode is `prompt` (the default use-case), the add-on uses Immich’s **contextual search** capability to find images matching the prompt. Immich leverages CLIP (Contrastive Language-Image Pretraining) models for free-form image search. The add-on will call Immich’s search API (e.g. `POST /api/searchAssets` or similar) with the prompt as the query and `clip=true` to get a list of asset results. Immich’s CLIP search does not require the prompt words to appear in metadata; it returns images by semantic similarity to the prompt (e.g. searching “beach sunset” can find a photo of a beach at dusk even if not labeled). The module will request, say, *N* results (where *N* is the number of images to display, configured by the user). If Immich’s API allows specifying the number of results, it will do so; otherwise it may fetch a larger set and then select a random subset or the top N.
* **Random Images:** If the mode is `random`, the add-on will fetch random photos from Immich. Immich provides an endpoint (e.g. `POST /api/searchRandom`) to retrieve random assets, optionally filtered by criteria (like only favorites, within a date range, etc.). The add-on can simply ask for *N* random assets without any specific query – this leverages Immich’s backend to do a database random sampling of assets. For example, setting the request body `{"size": N}` on `searchRandom` will return that many random images from the library. This is more efficient than pulling all assets and picking ourselves. The user could also configure filters (like `isFavorite: true` to only show favorites, or an album ID) – the module will include those if specified.
* **“On This Day” Memories:** If the mode is `on_this_day`, the add-on will retrieve photos taken on today’s date in past years. Immich has a Memories feature similar to Google Photos that can return “On This Day” images. The module will call the appropriate Immich API (likely `GET /api/searchMemories?type=on_this_day&for=<today>` or a dedicated endpoint) to get the assets for the current date. This typically returns a collection of assets (possibly grouped by year). The add-on can then take up to *N* of those results (if more are returned than needed, perhaps choose randomly or the most recent years for variety). This mode gives a daily nostalgia slideshow using the user’s own photos from the same day in history.
* **Fallback/Combination:** The design can allow hybrid strategies. For example, if prompt-based search yields too few results (or none), the module could automatically fall back to random images to fill the quota. This ensures the dashboard always has a full set of images. Similarly, one could combine “on this day” with a prompt (e.g. prompt could be “memories” and still use CLIP search) – but such advanced combos are beyond the initial scope, and the simpler distinct modes are preferred for clarity.

The Image Selection module is implemented in a class like `ImageSelector` which has methods corresponding to each mode. It uses an `ImmichClient` (see below) to perform the actual API calls to Immich. The output of this module is a list of **asset identifiers** (and possibly additional metadata like filenames or thumbnails paths) for the next stage.

## 3. Immich API Client (Asset Retrieval & Caching)

Fetching images from Immich is handled by a dedicated **Immich API Client** module, responsible for all HTTP interactions with the Immich server. This module abstracts the Immich REST API endpoints:

* **Authentication:** The client is configured with the Immich server base URL and an API key (provided in the config). Immich API keys are generated via the user’s account in Immich. The client will attach this key in the Authorization header or as required by Immich (ensuring secure access to the photos).

* **Search Queries:** The client provides methods used by the Image Selector: e.g., `search_by_clip(prompt, limit)` to call the search endpoint with a prompt, `search_random(count, filters)` to call the random endpoint, and `get_memories(date)` for the on-this-day query. These methods return structured results (lists of asset IDs and info). For instance, `search_by_clip` might issue a `POST /api/searchAssets` with a JSON body containing the query string and `clip: true`, receiving a JSON of matching assets. The client will parse this JSON to extract asset IDs or relevant fields.

* **Asset Metadata:** In some cases, the selected assets might need additional info before download (e.g., to get a direct link or to verify types). Immich’s API has endpoints like `GET /api/assets/<id>` or `GET /api/assetInfo/<id>` to fetch metadata for a given asset. The client can call these if necessary. However, Immich often returns enough info in search results (like a thumbnail path or the asset’s original file path on server) so this extra step may be optional.

* **Downloading Images:** The client handles **asset retrieval** – downloading the actual image files. To keep things efficient, the add-on will download **thumbnails or resized images** rather than full-resolution originals. Immich supports requesting different sizes: for example, a **`viewAsset`** endpoint can return an image binary given an asset ID and a size parameter (`thumbnail`, `preview`, or `full` size). The client will call something like `GET /api/asset/<id>/view?size=thumbnail` to retrieve a small version of each photo. This keeps bandwidth and processing low while still providing a clear image for the dashboard. If no thumbnail is available, it may fallback to preview size. Each image download is saved to disk.

* **Caching and File Management:** Downloaded images are saved into the Home Assistant **www folder**: `/config/www/daily_photos/`. Home Assistant serves files from `/config/www` at the URL path **`/local/`** (e.g., a file at `/config/www/daily_photos/img1.jpg` is accessible at `http://<HA>/local/daily_photos/img1.jpg`). The add-on ensures this directory exists and then writes the images (e.g., JPEG files) into it. It may name files in a predictable way (like `photo1.jpg, photo2.jpg, ...` or include the date in the filename). Because the files are in `/config/www`, they persist across add-on restarts and are readily available to Lovelace UI without any further action.

  The add-on can maintain a cache policy such as: remove yesterday’s images when updating to new ones, to avoid clutter. This could be done by clearing the `daily_photos` folder each run before saving new images, or by overwriting files with consistent names. Alternatively, it might keep a history (e.g. keep images for the past X days) if desired, but simplest is to replace the set daily. Since the process runs at most once a day, the overhead of downloading a handful of thumbnails is small. Immich’s use of thumbnails and the limited number of files ensure performance is not an issue. (For reference, Immich can generate and serve thumbnails for quick viewing – this add-on leverages that to avoid heavy load).

* **Error Handling:** The client will handle HTTP errors or timeouts. For example, if Immich is unreachable, the client methods should throw an exception or return a failure status, which the orchestrator can catch. The system could then decide to retry after some time or skip the update for that cycle. Robust logging will be in place to troubleshoot (e.g., log if an API call returned an error or if JSON was malformed).

## 4. Home Assistant Integration

Integration with Home Assistant occurs *passively* through files and *optionally* through the HA API for text updates:

* **Static Image Access:** By storing images in `/config/www/daily_photos/`, we ensure Home Assistant can serve them as static files. The Lovelace UI can be configured to display these images using standard cards. For example, the user might use a **Picture Elements** or **Gallery card** to show all images in that folder. (Custom cards like the Gallery card can even display a folder of images.) Alternatively, the user can explicitly list the image URLs in a Picture Glance or Picture Entity card – since the filenames are known or predictable, they can reference `/local/daily_photos/photo1.jpg`, etc. The main point is that once images are in `www`, **Home Assistant treats them as publicly accessible resources**, making the slideshow straightforward to embed on dashboards. No custom camera entities or streaming is needed, simplifying the design.

* **Prompt Display (Text Entity):** We have an optional feature to expose the **current prompt** (the caption or theme for the slideshow) within Home Assistant. There are two approaches:

  1. **Update an `input_text` entity:** The user can create an `input_text` entity in Home Assistant (or the add-on can be configured with one). After generating the prompt, the add-on could call Home Assistant’s REST API to set this entity’s state to the prompt string. For example, an API call to `/api/services/input_text/set_value` with JSON `{"entity_id": "input_text.daily_prompt", "value": "Beach Sunset"}` can update the value. This would require the add-on to have access to Home Assistant’s API – typically by obtaining an authentication token (the user can provide a Long-Lived Access Token, or if running in supervised mode, use the internal supervisor token). Once updated, the `input_text.daily_prompt` state is available in Home Assistant; the user can then include it in a **Markdown card** or other UI element to display the text. This method is clean because it leverages Home Assistant’s state system (the prompt can also be used in automations or voice assistants, etc.).
  2. **Write to a file or HTML for UI:** If one prefers not to use the API, the add-on could output the prompt to a file, e.g., `/config/www/daily_photos/prompt.txt` or `prompt.json`. The dashboard could then use a **File Sensor** or **REST sensor** to read that file’s content. For instance, Home Assistant’s `file` sensor can monitor a text file and expose its contents as a sensor state. The Markdown card can then show that sensor. Another hacky method is an `iframe` card pointing to an HTML file in `www` that displays the prompt, but that’s generally not needed if the input\_text or sensor approach is available.

  The choice of approach is configurable. For simplicity, many users might skip showing the prompt, but it’s a nice touch to know what the “search query” was. In the architecture, this is handled by an **Integration module** (e.g., `HAIntegrator`), which knows how to send data to Home Assistant if enabled. This module would use the Home Assistant **Supervisor or Core API**. (Since this is an add-on, one way is to use the Supervisor’s internal DNS name `http://homeassistant` and a token to call the Core API). We ensure that any such token or credential is provided via config and not hard-coded.

In summary, Home Assistant integration points are kept simple and robust:

* **Images**: via static served files (no special entity logic needed).
* **Prompt text**: via an HA entity or file sensor (optional).

This minimizes the chance of breaking with Home Assistant updates, as we rely on standard mechanisms. The Lovelace UI will be configured by the user to utilize these outputs (the add-on could provide example Lovelace configuration in docs, e.g., a gallery card that references `/local/daily_photos/`).

## 5. Configuration Format and Options

Configuration is done via a file in the add-on’s `/config` directory (since the add-on can read the Home Assistant config folder). This could be a YAML or JSON file (YAML is user-friendly for editing). The add-on will load this config at startup and use it to initialize all components. Key configuration options include:

* **Immich Connection:**

  * `immich_url`: Base URL of the Immich server (e.g. `http://192.168.1.100:2283` or a domain name).
  * `immich_api_key`: The API key or token for authenticating to Immich. (This should be kept secret; the user generates it in Immich and pastes it here. The add-on will supply it in API calls, typically in an `Authorization: Bearer <token>` header or as required.)

* **Prompt Settings:**

  * `prompt_source`: Which prompt generation method to use. Possible values: `static_list`, `random_file`, `ha_input_text`, `llm_openai`, `llm_local`.
  * Additional fields depending on the source:

    * If `static_list`: provide `prompts:` as a list of strings in the config (or it could read from a file). The add-on might cycle through them sequentially or randomly – possibly add another option like `prompt_cycle: sequential|random`.
    * If `random_file`: provide `prompts_file: "/config/prompt_ideas.txt"` (path to a text file).
    * If `ha_input_text`: provide `prompt_entity: "input_text.my_prompt"` and optionally the Home Assistant API details (if not using Supervisor token). Possibly an `ha_token` if needed.
    * If `llm_openai`: provide `openai_api_key`, and maybe model or prompt template to use for ChatGPT. For example, `openai_model: "gpt-3.5-turbo"` and a prompt template like `openai_prompt: "Suggest a theme for a family photo slideshow for {date}."`
    * If `llm_local`: provide `llm_endpoint` (e.g. `http://localhost:11434/generate`) or any needed parameters for the local model (like model name if Ollama supports multiple).

* **Image Selection Mode:**

  * `image_mode`: How to pick images. Values: `prompt`, `random`, `on_this_day`.
  * If `image_mode` is `random`, optional sub-options could include filters like `random_favorites_only: true` or `random_album: <album name or id>` if we want to only show certain subsets.
  * If `image_mode` is `on_this_day`, one could optionally specify a year range or a toggle like `include_today_photos: false` (depending on user preference to include the current year’s photos or not).

* **Number of Images:**

  * `count: 5` (for example). Default could be 5 if not specified. This many images will be retrieved and displayed. The Lovelace card would ideally handle showing a set of images; if using a picture entities card, the user can template in however many they configured. Keeping this number moderate (e.g., 3–10) is wise for layout and performance.

* **Update Schedule:**

  * `schedule: "0 7 * * *"` for example. This would use cron syntax to specify when the slideshow updates. In this example, it’s set to run daily at 07:00 (7 AM) every day. The add-on will interpret this string using a cron parser. We plan to use a Python library (like **croniter**) to parse and compute the next run times. Cron syntax gives flexibility – users can do hourly (`0 * * * *`), specific days, etc. If the user doesn’t want cron, we could allow simpler alternatives like an interval (every X hours) or a once-daily at a fixed time (with separate `daily_time: "07:00"` option), but supporting full cron is more powerful.
  * The add-on will likely run as a daemon process that sleeps or waits until the next cron time, then triggers an update. (Alternatively, we could use the Home Assistant Supervisor’s scheduler if it exists, but it’s simpler to handle internally).

* **Other Options:**

  * Possibly `retain_days` or `cleanup: true/false` to control if old images are removed.
  * Logging level, etc., if needed.
  * If the add-on should integrate with HA API (for input\_text updates), config might include an `ha_url` (usually `http://homeassistant:8123` internally) and an `ha_token` (if not using the Supervisor service role).

**Example (YAML) Configuration:**

```yaml
immich_url: "http://10.0.0.5:2283"
immich_api_key: "abcd1234efgh5678"  # Immich API key

prompt_source: "llm_openai"
openai_api_key: "sk-XXXXXXXXXXXXXXXXXXXX"
openai_model: "gpt-3.5-turbo"
openai_prompt: "Provide a short theme for a photo slideshow for today ({date})."

image_mode: "prompt"         # use the prompt to search images
# image_mode: "random"      # alternative modes
# image_mode: "on_this_day"

count: 5                     # number of images to fetch

schedule: "0 7 * * *"        # cron schedule for daily at 7:00 AM

# Optional: If showing prompt in HA
ha_prompt_entity: "input_text.daily_slideshow_prompt"
ha_token: !secret ha_api_token   # reference to a secret stored elsewhere
```

The add-on will validate this config on startup (e.g., ensure required fields for the chosen modes are present). By using a file under `/config`, users can edit it easily via the file editor or Samba, and then just restart the add-on to apply changes. (If we wanted to be fancy, the add-on could watch the file for changes and auto-reload, but that’s optional).

## 6. Modular Code Structure and Components

The implementation is structured as a Python package with clear modules for each function. This makes the code easier to test and extend. Below is a breakdown of the main components and their roles:

* **PromptGenerator Package:** Contains sub-modules for each prompt source. For example:

  * `prompt_sources/static_list.py` – handles cycling through a static list from config.
  * `prompt_sources/random_file.py` – reads a file of prompts and picks one.
  * `prompt_sources/ha_input.py` – connects to Home Assistant API to fetch the value of an input\_text entity.
  * `prompt_sources/llm_openai.py` – uses OpenAI API to generate a prompt (likely using `openai` Python library or simple HTTP requests).
  * `prompt_sources/llm_ollama.py` – calls a local LLM endpoint (e.g., HTTP request to an Ollama server).
  * `prompt_sources/calendar_prompt.py` – (optional) uses calendar events to form a prompt (could combine with another source).
    All these would implement a common interface, e.g., each has a function `get_prompt(date_today) -> str`. The Prompt Generation module in the orchestrator just calls this interface without worrying which one is underneath.

* **ImmichClient Module:** Implemented as a class (e.g., `ImmichClient` in `immich/client.py`). This class manages all calls to Immich’s API:

  * `search_assets_by_prompt(prompt, limit)` – uses Immich’s search with CLIP.
  * `search_random_assets(limit, filters)` – calls the random search API to get random assets.
  * `get_memories(date)` – calls the memories API for on-this-day.
  * `get_asset_thumb(asset_id)` – fetches a thumbnail image (calls `viewAsset?id=asset_id&size=thumbnail`). Possibly returns the binary or saves directly.
  * `download_asset(asset_id)` – if needed to get full image (likely not needed for our purpose).
    The client will likely use Python’s `requests` library to make HTTP calls. It will also include helper methods like setting auth headers (e.g., `self.session.headers.update({"Authorization": f"Bearer {api_key}"})`). By encapsulating this, if Immich changes their API, we only update this module. Also, it ensures all HTTP interactions (and error parsing) are in one place.

* **ImageSelector Module:** A component that contains the logic described in section 2. It could be a class like `ImageSelector` or simply a set of functions, but likely a class with the mode and client as dependencies. For example, `ImageSelector.select_images(prompt: str) -> list[Asset]` will decide which mode to use and call the ImmichClient accordingly. If mode is `prompt`, it calls `client.search_assets_by_prompt(prompt, N)`; if `random`, call `client.search_random_assets(N, filters)`; if `on_this_day`, call `client.get_memories(today)` and take N results. The result is a list of **Asset descriptors** – perhaps a simple dict or small class containing at least the `asset_id` and maybe a file name or URL. This selector does not itself download the images, it just uses ImmichClient to get asset metadata.

* **CacheManager / FileManager Module:** Responsible for handling the local file storage. This can be in `slideshow/cache.py` for instance. Its responsibilities:

  * Ensure the output directory exists (creating `daily_photos` folder if not present).
  * Clean up old files if needed (e.g., remove yesterday’s images). Alternatively, it could be instructed to overwrite specific filenames.
  * Provide a method `save_image(asset_id, image_data)` that writes the binary content to a file. Filenames could be static like `image_1.jpg, image_2.jpg, … image_N.jpg` each run (simplest approach, reuse names daily). Another approach is include the date, e.g., `2025-05-20_1.jpg` for today’s first image – but then cleaning old ones becomes important. Using fixed names and replacing them daily is straightforward and ensures Lovelace is always pointing to the same URLs (which might even be cached by the browser – though one might add a cache-buster query param if needed).
  * This module isolates file I/O from the rest of the logic. It could also handle writing the prompt text file if that approach is used. E.g., `save_prompt_text(prompt_str)` writes `prompt.txt`.

* **HA Integration Module:** If we implement the optional Home Assistant API interactions, this could be a small module (e.g., `integration/ha_updater.py`). It might have:

  * A function to call Home Assistant’s `/api` to update an entity. Possibly using the `requests` library as well, with the URL and token from config. For example, a method `update_input_text(entity_id, value)` that performs the POST request as described earlier.
  * If reading from an HA input\_text for the prompt source, that could either be here or in the prompt\_sources module. It might make sense to reuse some code – for instance, a generic method `get_ha_state(entity_id)` that calls the HA API’s GET state endpoint. The `HAInputPromptSource` could use that.
  * This module should handle connection errors gracefully (e.g., if HA is restarting and the API call fails, just log a warning).

* **Scheduler/Orchestrator:** The main program (e.g., in `main.py`) orchestrates all the above. When the add-on container starts, `main.py` will:

  1. Load configuration (using a `config.py` helper to parse YAML/JSON and provide a config object).
  2. Initialize components: e.g., instantiate the appropriate Prompt Source class based on config, create the ImmichClient with URL and API key, instantiate ImageSelector with ImmichClient and mode, instantiate CacheManager, and prepare HA updater if needed.
  3. Enter a scheduling loop: If a cron schedule is provided, compute the next run time. The app can either sleep until that time or use a loop that checks periodically. We might use the `croniter` library to get the next timestamp from the cron expression. For example: on startup, compute next run = croniter(expr, now).get\_next(datetime). Then sleep (or wait) until that time. At the scheduled time, call the update routine and then compute the next and repeat. (If the schedule is daily and we don’t want a full event loop, a simple approach is to sleep for 24h; but cron allows complex schedules, so better to calculate next event precisely).
  4. Perform update routine:

     * Generate prompt via PromptGenerator module (`prompt = prompt_source.get_prompt(today)`)
     * Log the prompt and perhaps store it.
     * Use ImageSelector: e.g., `assets = image_selector.select_images(prompt)` which returns list of asset IDs (and possibly some metadata).
     * For each asset in that list: call `image_data = immich_client.get_asset_thumb(id)` (or similar) to retrieve the image binary. Then call `cache_manager.save_image(i, image_data)` to save it as `daily_photos/image_i.jpg`. (The index `i` or some ordering from 1 to N can be used).
     * Once all images are saved, call `ha_integration.update_prompt(prompt)` if that feature is enabled, to update the HA text entity or file.
     * Log a success message. If any step fails, catch exceptions: e.g., if Immich search failed, we could retry after a short delay or skip updating (optionally, one could implement a retry mechanism or a fallback to random).
  5. Remain running: After an update, the scheduler computes the next time and waits accordingly. We ensure the process doesn’t exit after one run (unless the schedule was one-shot). The add-on thus runs continuously in the background.

* **Logging & Debugging:** Throughout modules, use Python’s logging to record key events (for example: “Generated prompt: ‘Beach Day’”, “Found 5 assets from Immich for prompt”, “Saved 5 images to /config/www/daily\_photos”, “Updated input\_text.daily\_slideshow\_prompt entity”). This will help users see what’s happening via the add-on logs in the Supervisor panel.

This modular design ensures each part of the logic is testable. For instance, one could unit test the `StaticPromptSource` easily by feeding a list and checking output, or test `ImmichClient.search_random_assets` by mocking an Immich response. The clear separation also means users could replace components if needed (e.g., swap out OpenAI with another AI by adding a new module, without touching the rest of the code).

## 7. Proposed Folder Structure

Below is a suggested project structure for the add-on’s source code and related files. This helps organize the code by feature and also fits into the Home Assistant add-on format (with a Dockerfile and config):

```
hass_immich_addon/             # Root folder of the add-on
├── Dockerfile                 # Dockerfile to build the add-on image
├── config.yaml (or config.json)  # Add-on configuration schema if needed (for UI)
├── requirements.txt           # Python dependencies
├── README.md                  # Documentation for users
└── hass_immich_addon/         # Python package (source code)
    ├── __init__.py
    ├── config.py              # Config parsing and dataclasses
    ├── main.py                # The main entrypoint of the add-on
    │
    ├── prompt_sources/        # Package for prompt generation strategies
    │   ├── __init__.py
    │   ├── static_list.py
    │   ├── random_file.py
    │   ├── ha_input.py
    │   ├── llm_openai.py
    │   ├── llm_ollama.py
    │   └── calendar_prompt.py
    │
    ├── immich/                # Package for Immich API interactions
    │   ├── __init__.py
    │   └── client.py          # ImmichClient class definition
    │
    ├── slideshow/             # Package for slideshow-specific logic
    │   ├── __init__.py
    │   ├── selector.py        # ImageSelector class
    │   └── cache.py           # CacheManager for file I/O
    │
    └── integration/           # Package for Home Assistant integration (optional)
        ├── __init__.py
        └── ha_updater.py      # Functions to update HA entities (if used)
```

In this layout:

* The **Dockerfile** at root will define the base image (likely a slim Python image or the Home Assistant base Python image) and copy the `hass_immich_addon` package into the container. It will install the `requirements.txt` and set the command to run `python -u -m hass_immich_addon.main` (or similar) when the container starts.
* The **Python package** `hass_immich_addon` contains all the logic. By structuring it with sub-packages, we logically separate concerns. For example, the prompt source implementations are all in one directory; the Immich API client is isolated in its own; etc. This makes the repository easy to navigate.
* We include a **requirements.txt** listing needed libraries (e.g., `requests` for HTTP, `croniter` for cron parsing, possibly `PyYAML` if parsing YAML config, `openai` if using OpenAI SDK, etc.). This file is used in Dockerfile to install deps.
* Optionally, a **config.yaml** at root could define the schema for Home Assistant add-on options (if we wanted to allow config via the UI rather than an external file). However, since we allow a custom YAML, we might not integrate with HA’s UI config and instead instruct users to edit our YAML in `/config`. (Home Assistant add-ons typically have an `options` section in addon config, but complex nested config may be easier in a separate file).

The folder structure above is an example and can be adjusted, but it illustrates the clear grouping:
each major feature has its place, making it easier to extend (e.g., adding a new prompt source file doesn’t affect others) and to maintain. This approach follows good Python project practices (avoiding one huge script, and instead grouping related functions in modules).

## 8. Performance and Reliability Considerations

Designing for performance and reliability ensures the add-on runs smoothly on the typically modest hardware of Home Assistant (Raspberry Pis, etc.) and doesn’t disrupt either Immich or Home Assistant:

* **Lightweight Operation:** The add-on’s work is infrequent (e.g., daily). CPU and memory usage should be minimal. The heaviest tasks might be: an API call to an LLM (which is network I/O, done outside), and Immich’s CLIP search query. The CLIP search on Immich’s side could be somewhat intensive (embedding the prompt and comparing to images), but doing it once a day is negligible in impact. On the add-on side, handling a JSON response of a few items and downloading a few small images is trivial for modern hardware. Even on a Raspberry Pi, downloading 5 thumbnails and writing to disk will finish in a couple of seconds.

* **Use of Thumbnails:** We intentionally retrieve low-resolution images. This avoids large memory usage and bandwidth. For example, if thumbnails are a few tens of KB each, 5–10 images are only a few hundred KB total, which is fine. If the user’s dashboard displays them fullscreen, the quality might be a bit lower, but this is usually acceptable for a slideshow. (We could make the size configurable – e.g., allow `size: preview` vs `thumbnail` – preview might be a medium resolution). By default, thumbnails suffice for quick glances. This design choice prevents slow loading on the dashboard and reduces load on the Immich server.

* **Caching and Disk I/O:** Writing to `/config/www` means the data is stored on the Home Assistant host (often an SD card or SSD). Writing a few files a day is low wear. We do not continuously write or read, so there’s no significant I/O burden. We will also avoid writing if not necessary (e.g., if re-using file names, each day’s files overwrite the old ones rather than accumulating new files, unless user configures otherwise).

* **Network Reliability:** The add-on depends on reaching the Immich server (which might be local network or remote) and possibly external APIs (OpenAI). If those calls fail (network down, server down), the system should handle it gracefully:

  * We will implement timeouts on HTTP requests (to avoid hanging indefinitely). If a timeout or error occurs during search or download, the add-on can catch it. Potential strategies: skip this cycle (leave the previous images in place) and try next scheduled time, or retry after a short delay. Given it’s not mission-critical to update at that exact minute, logging the failure and retrying on the next cron run might be enough.
  * If an LLM call fails, we can fall back to a simpler prompt (e.g., use last prompt or a default static prompt) so that the image search can still proceed.
  * The add-on will produce log messages for failures, visible to the user in Supervisor -> Add-on logs, so they can investigate (e.g., “Could not reach Immich server at URL… will retry on next schedule”).

* **Consistency:** Since Home Assistant may boot up at random times, we consider what happens on start. If the add-on is set to run at a specific cron time, and Home Assistant (and thus the add-on) restarts just before that time, the scheduling will pick it up normally (since we calculate next event from current time). If the restart happens after the scheduled time was missed, we might consider running immediately on startup if a run was missed (this could be a feature: e.g., if HA was offline at 7:00, do the update at next opportunity). Croniter can help to calculate the next occurrence even if one was missed (or we could simply run on start always, then subsequently on schedule). We’ll document whichever approach we choose.

* **Integration Reliability:** Using static files for images means there’s **no runtime dependency** between Home Assistant’s front-end and our add-on. Even if the add-on is stopped, the last images remain available in `/www`. This is robust – the dashboard will still show the last set of images (they just won’t update until the add-on runs again). Similarly, for the prompt text: if using an `input_text`, that state remains in Home Assistant once set. Thus a failure or downtime in the add-on doesn’t break the frontend, it just means it’s not updating. This decoupling is intentional to reduce live coupling.

* **Security:** The add-on handles sensitive info: API keys for Immich and possibly OpenAI. We will ensure these are **not logged** (e.g., never print the API keys). The config file could be stored with appropriate permissions. Communication with Immich can be over HTTPS if the Immich URL is HTTPS (recommended if not on a fully trusted network). OpenAI calls are HTTPS by default. No user personal data is sent anywhere except Immich and optionally OpenAI (the prompt may include something like a date or event name; users should be aware if they use OpenAI, that prompt goes to OpenAI servers). If the user is privacy-conscious, they can stick to local prompt sources or static ones.

  * The add-on container will run with minimal permissions – it only needs access to `/config` (for config and saving files) and internet access. It doesn’t need host hardware access or elevated privileges. In the add-on config, we won’t request things like `privileged` mode.
  * If using Home Assistant API, the token provided should have limited scope (a long-lived token typically has full access to call any service, so it is sensitive – user should treat it like a password). Alternatively, since this is a local integration, one could create a dedicated Home Assistant user with only the ability to edit that one input\_text (though HA doesn’t granularly permission entities easily). This is something to note in docs.

* **Scheduling Accuracy:** The use of cron expressions allows flexible timing. Libraries like `croniter` are reliable for this. We should be mindful of timezones – Home Assistant runs typically in local time. Cron by default we interpret in the system’s local time (the add-on container should have the same timezone as HA if configured, or we can explicitly handle TZ). If a user wants to update at midnight local time, we should ensure that works correctly. We might use Python’s `schedule` library as an alternative, but it doesn’t natively support cron syntax, so croniter + our own sleep loop is fine.

  * We will also handle DST changes gracefully (croniter can handle next occurrences across DST boundaries properly by using aware datetimes). These are minor details but contribute to reliability.

* **Concurrent Operation:** It’s expected only one instance runs, triggered by time. We won’t run overlapping tasks. If a schedule happens to be very frequent (say every 5 minutes, though that would be unusual for a slideshow), we would ensure that if one run hasn’t finished when the next is due, we either skip the next or queue it. But given daily or hourly scales, we likely won’t hit that scenario. In any case, our code can include a simple lock (e.g., don’t start a new update if one is still in progress). Each update involves network calls which are the slowest part; those are relatively quick (maybe a couple seconds per image).

Overall, the design choices (limited image count, thumbnails, single daily schedule, decoupled file serving) make the add-on efficient and reliable for long-term use. Users can trust it won’t hog resources on their Home Assistant instance, and it will degrade gracefully (if something fails, last known good images stay in place rather than a broken dashboard).

## 9. Future Extensibility and Ideas

We anticipate several enhancements and extensions could be built on this architecture in the future:

* **Additional Prompt Logic:**  The system could incorporate more advanced prompt generation. For instance, integrating with weather data (“if it’s rainy, show cozy indoor memories”) or news (though that might be far-fetched for personal photos). Because the prompt generator is modular, one could add, say, a **“thematic cycle”** source that uses the day of week or month to choose themes (e.g., beach themes every Sunday in summer, etc.). Another idea is using **ML image analysis** on the Immich library to identify themes and then have the prompt pick among those themes.

* **Multiple Slideshows / Multi-Instance:** Currently the add-on focuses on one set of images per day. In the future, one might want to support multiple concurrent slideshows (for example, if a user has multiple displays or dashboard views, each with a different theme – one showing “on this day”, another showing “random favorites”). This could be achieved by allowing multiple config profiles within one add-on, or simply by running multiple instances of the add-on (though Home Assistant’s add-on system usually expects one instance). A more elegant solution could be to extend the add-on to handle multiple *sets* of images: e.g., configuration could allow defining two or more “slideshow outputs”, each with its own prompt source, mode, and output directory. The add-on could then populate multiple folders (e.g., `daily_photos1`, `daily_photos2`) and the UI can have two gallery cards. This adds complexity but is a possible extension for enthusiasts.

* **From Add-on to Integration:** In the long run, if Home Assistant gains deeper integration with Immich, some of this functionality might be available as a native integration (component). For example, a Home Assistant integration could create a `camera` entity that cycles through Immich images, or an `image` entity like the custom integration by outadoc (which created entities for albums). However, running as an add-on has benefits: we can leverage external libraries and even heavy AI models without worrying about Home Assistant’s core restrictions, and we run in isolation. That said, we might consider adding an MQTT or WebSocket interface so that the add-on could be triggered or controlled by Home Assistant automations. For instance, an automation could send an MQTT message to change the prompt on demand (imagine pressing a “Next Theme” button that tells the add-on to immediately fetch a new random prompt and images). The architecture can accommodate this – the main loop could listen for such triggers if implemented.

* **UI/UX Improvements:** We could develop a **Loveseat (Lovelace) custom card** for slideshows that specifically knows how to cycle through images in a folder or entity. Right now, users might rely on a gallery or a stack of picture cards with an automatic refresh. A custom card could add nice features like crossfade transitions or a slideshow play/pause control. This would be a separate project (front-end JavaScript), but the add-on’s output (folder of images and maybe a JSON manifest) could feed into it.

* **Calendar-Driven Slideshows:** Expanding on the calendar idea – imagine the add-on automatically shows specific albums or collections on certain dates (birthday albums on family birthdays, holiday albums in holiday seasons). This would require mapping dates to album IDs or tags. The config could allow rules, like “on date X, use album Y”. Since Immich supports albums and tags, the ImageSelector could be extended to filter by those when needed. This is a specialized use-case but demonstrates the flexibility of using Immich’s metadata (faces, people, albums, tags) for selection criteria.

* **Scalability and Frequency:** If a user wanted to update images **more frequently than daily** (say every hour new random images), the system can handle it – just a config change. Immich can serve the requests and the overhead is still small. In the future, if Immich’s API or the library is large, one might consider not downloading on each run but rather pre-fetching more images and cycling through them. For example, the add-on could fetch 50 images once and then just shuffle them periodically. However, that introduces complexity of state (need to store unused images). Given Immich is quite efficient at search, on-demand fetch is simpler. But it’s possible to implement caching of asset lists if needed.

* **Support for Videos or Other Media:** Immich also stores videos. Currently, a slideshow might skip videos or treat them as static (maybe show a thumbnail). In the future, perhaps the slideshow could play short videos or Live Photos. This would need more integration on the front-end (HA would need to be able to display it, perhaps via the `video` platform or a video file in /www). The architecture could be extended by checking asset type (if Immich returns a type = VIDEO, maybe handle differently). This is an edge case and likely not in initial scope, but noteworthy for completeness.

In summary, the modular design sets up a strong foundation. New prompt sources, new image selection criteria, or new integration methods can be added with minimal impact on existing code. The daily photo frame concept can evolve with user needs and improvements in both Home Assistant and Immich. The architecture document, much like the code, is meant to be living – open to future enhancements while maintaining clarity and reliability in its current form.

## 10. Dockerization and CI/CD Pipeline

To deliver this add-on, we package it in a Docker container and automate the build process:

* **Docker Image:** The provided `Dockerfile` will likely use a base image like `python:3.11-slim` or the Home Assistant Base Image for add-ons (which is a minimal Alpine or Debian with Python). Using an HA base image can simplify things like logging and application structure, but a plain Python image works as well. We will `COPY` the source code into the image and run `pip install -r requirements.txt` to install dependencies. The image doesn’t need much else – it’s essentially a small Python app. The entry point (`CMD`) will launch the `main.py`. For example:

  ```dockerfile
  FROM python:3.11-slim  
  WORKDIR /app  
  COPY hass_immich_addon/ /app/hass_immich_addon/  
  COPY requirements.txt /app/  
  RUN pip install -r requirements.txt  
  CMD ["python", "-u", "-m", "hass_immich_addon.main"]  
  ```

  (We use `-u` for unbuffered logging, so logs show up live in HA.)
  The image will declare needed labels for Home Assistant add-on if necessary (like `LABEL io.hass.type=addon`). It will also specify in the add-on configuration what ports or mappings we need – in our case, we likely **do not need any ports** exposed, since we are not serving a web service; we just run internally. We do need access to `/config` so the add-on config in HA will include `"map": ["config:rw"]`.

* **Multi-Architecture Support:** Home Assistant runs on different architectures (amd64 for most servers, arm32/arm64 for Raspberry Pi). Our GitHub Actions CI will build for multiple platforms. We can use Docker’s buildx to create a multi-arch manifest. For example, using QEMU, we can build amd64, arm/v7, and arm64 images. The GitHub Actions workflow will likely be triggered on git tags (for version releases) and use a matrix of architectures. We’ll push the image to a container registry (perhaps Docker Hub or GitHub Container Registry) under a name like `hass-immich-addon:<version>`.

* **Continuous Integration:** We will have linting and testing in CI as well. Before building the image, the workflow can run Python linters or unit tests (if we add some). This ensures code quality. After that, the action logs in to the registry and builds and pushes the image. The resulting image tag can be referenced by the add-on’s configuration. If this is a community add-on, the add-on `config.json` (not to be confused with our YAML config) will have the image URL. Home Assistant’s supervisor then pulls the new image when the add-on is updated.

* **Versioning:** We’ll use semantic versioning (e.g., 1.0.0 for initial release). The GitHub release/tag triggers the action for building that version. The Docker image might have tags `:1.0.0` and also `:latest` pointing to the same. The add-on repository can be set up so that users can add it to Home Assistant and get updates through the Supervisor UI.

* **Maintenance:** With the modular setup, updates (like adding a new prompt source) only require changing the Python code and possibly the config. The CI/CD makes it easy to deploy those changes.

In essence, the Dockerization and CI portion ensure that our modular Python code is delivered in a consistent environment. The add-on will run the same regardless of the host OS, and users can easily install it without dealing with Python environments themselves. The GitHub Actions automation speeds up releasing new versions and maintaining support for all devices Home Assistant runs on.

By adhering to these architectural plans, the `hass-immich-addon` will be a **robust, extensible, and user-friendly** solution to enjoy one’s photo library dynamically on Home Assistant – turning it into a smart, AI-assisted digital photo frame. All design choices aim for clarity, reliability, and ease of use, ensuring a smooth experience for both developers and end users of the add-on.

**Sources:**

* Immich contextual CLIP search allows free-form image queries
* Immich API supports random photo retrieval with a specified count
* Immich “On This Day” memories can be fetched via the API for a given date
* Home Assistant serves files in `/config/www` at the `/local/` path for use in Lovelace
* Using cron expressions for scheduling (e.g., via `croniter`) simplifies timed executions
* Emphasis on modular project structure improves maintainability and clarity
