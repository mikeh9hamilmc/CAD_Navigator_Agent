import os
import json
import asyncio
from typing import Dict, Any, List

# Define the tools exactly as specified in AGENTS.md
SOLIDWORKS_TOOLS = [
    {
        "name": "create_new_part",
        "description": "Initializes a new SolidWorks part document."
    },
    {
        "name": "select_plane",
        "description": "Selects the Front, Top, or Right plane based on visual context or explicit command.",
        "parameters": {
            "type": "object",
            "properties": {
                "plane_name": {
                    "type": "string",
                    "description": "The name of the plane to select (Front, Top, Right)."
                }
            },
            "required": ["plane_name"]
        }
    },
    {
        "name": "start_sketch",
        "description": "Activates the sketching environment on the currently selected plane or face."
    },
    {
        "name": "draw_shape",
        "description": "Uses SolidWorks API commands to sketch basic entities (lines, circles, rectangles) based on inferred or provided dimensions.",
        "parameters": {
            "type": "object",
            "properties": {
                "shape_type": {
                    "type": "string",
                    "description": "The type of shape to draw (e.g., 'line', 'circle', 'rectangle')."
                },
                "dimensions": {
                    "type": "object",
                    "description": "Dictionary of dimensions needed for the shape (e.g., {'radius': 10} or {'width': 50, 'height': 20})."
                }
            },
            "required": ["shape_type", "dimensions"]
        }
    },
    {
        "name": "apply_feature",
        "description": "Executes 3D features (e.g., 'extrude_boss', 'cut_extrude') using the active sketch.",
        "parameters": {
            "type": "object",
            "properties": {
                "feature_type": {
                    "type": "string",
                    "description": "The type of 3D feature to apply (e.g., 'extrude_boss', 'cut_extrude')."
                },
                "parameters": {
                    "type": "object",
                    "description": "Dictionary of parameters for the feature (e.g., {'depth': 25.0})."
                }
            },
            "required": ["feature_type", "parameters"]
        }
    },
    {
        "name": "analyze_ui_state",
        "description": "A diagnostic tool to check if a sketch is fully defined or under-defined and report back to the user verbally."
    }
]

def get_agent_config() -> dict:
    """Returns the configuration for the Gemini Live API model."""
    return {
        "system_instruction": {
            "parts": [{
                "text": (
                    "You are CAD_Navigator_Agent, a SolidWorks assistant. "
                    "The user will give dimensions in meters and that is the unit you should use for all calculations and tool calls."
                    "CRITICAL RULE: When the user asks you to do something, IMMEDIATELY call the appropriate tool. "
                    "Do NOT describe what you plan to do before calling the tool. Do NOT narrate your thought process. "
                    "Call the tool FIRST."
                    "CRITICAL RULE: Only speak the [Tool Response] after the tool has been executed."
                    "Each user message is one command. Execute it with one tool call. Be concise."
                )
            }]
        },
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": "Puck"
                }
            }
        },
        "tools": [{"function_declarations": SOLIDWORKS_TOOLS}],
        "response_modalities": ["AUDIO"]
    }
