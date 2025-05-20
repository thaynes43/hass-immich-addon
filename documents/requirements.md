# hass-immich-addon Requirements 

I want a way to display photos from immich on my Home Assistant dashboard. My photo library is a mess though and I want to just use natural language queries to retrieve photos relevant to what is going on in my world around that day. 

## Core Requirements

1. **Automated Photo Selection**
   - Daily photo slideshow generation from Immich server
   - Support for multiple selection modes:
     - Prompt-based CLIP search
     - Random images 
     - "On This Day" memories
   - Configurable number of images to display (5-10 default)

2. **Prompt Generation**
   - Multiple prompt source options:
     - Static predefined list
     - Random from text file
     - Home Assistant input_text entity
     - Local LLM (e.g. Ollama)
     - OpenAI API
     - Calendar-based prompts (optional)
   - Fallback handling if primary source fails

3. **Image Management**
   - Efficient asset retrieval from Immich
   - Caching of thumbnails/low-res images
   - Storage in HA's www directory
   - Clean up of old cached images

4. **Home Assistant Integration** 
   - Display via Lovelace Gallery/Picture cards
   - Optional prompt display (input_text/markdown)
   - Configurable update schedule (cron syntax)
   - No exposed ports needed

5. **Configuration**
   - YAML/JSON config file support
   - Immich connection settings
   - Prompt source preferences
   - Image selection mode
   - Number of images
   - Update schedule

6. **Technical Requirements**
   - Dockerized Python application
   - Multi-architecture support (amd64, arm32, arm64)
   - Modular code structure
   - CI/CD pipeline for builds
   - Semantic versioning
   - Helm chart (optional) 
