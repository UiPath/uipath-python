# Travel planner agent with stdio mcp

Use LangGrahp with UiPath LLMs to automatically create a travel plan.
Shows the usage of stdio mcp.

## Debug

1. Clone the repository:
```bash
git clone
cd samples\travel-planner-local-mcp
```

2. Install dependencies:
```bash
pip install uv
uv venv -p 3.11 .venv
.venv\Scripts\activate
uv sync
```

3. Init uipath
```
uipath init
uipath auth
```

4. Create a `.env` file in the project root with the following configuration:
```env
UIPATH_URL=https://alpha.uipath.com/ada/byoa
UIPATH_ACCESS_TOKEN=xxx
UIPATH_TENANT_ID=6961a069-3392-40ca-bf5d-276f4e54c8ff
UIPATH_ORGANIZATION_ID=b7006b1c-11c3-4a80-802e-fee0ebf9c360
```

```bash
uipath run <entrypoint> <input> [--resume]
```

### Run

To classify a ticket, run the script using UiPath CLI:

```bash
uipath run agent '{"message": "Help me plan a ski vacation on a hard track." }'
```

### Input JSON Format

The input ticket should be in the following format:
```json
{
    "message": "Plan a trip to...",
}
```

### Output Format

The script outputs JSON with a markdown summary:
```json
{
    "summary": "# Final Report\n\n## Ski Vacation Options\n\n### 1. Aspen Snowmass\n- **Location:** Colorado, USA\n- **Elevation:** 12,510 ft\n- **Trails:** 362\n- **Best For:** Intermediate to advanced skiers\n- **Season:** November to April\n- **Highlights:** Aspen Snowmass features four mountains with varied terrain, luxury amenities, and a vibrant après-ski scene.\n- **Weather Forecast:** Currently unavailable, but typically sunny and around 75°F based on seasonal averages.\n\n### 2. Vail\n- **Location:** Colorado, USA\n- **Elevation:** 11,570 ft\n- **Trails:** 195\n- **Best For:** Intermediate to advanced skiers\n- **Season:** November to April\n- **Highlights:** Vail is known for its Back Bowls, European-style village, and extensive groomed terrain.\n- **Current Weather:** 25°F, Light Snow with 70% humidity and 8 mph winds. Current snow depth is 30 inches.\n\nBoth Aspen Snowmass and Vail offer excellent facilities and challenging tracks for advanced skiers. You can enjoy a mix of thrilling ski experiences and luxurious amenities. Vail currently has favorable skiing conditions with fresh snow, making it an attractive option for your ski vacation."
}
```
