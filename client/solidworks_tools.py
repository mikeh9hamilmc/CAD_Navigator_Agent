import win32com.client
import pythoncom
import asyncio

def get_sw_app():
    """Initializes COM and retrieves the active SolidWorks application instance."""
    pythoncom.CoInitialize()
    try:
        swApp = win32com.client.Dispatch("SldWorks.Application")
        swApp.Visible = True
        return swApp
    except Exception as e:
        print(f"Failed to connect to SolidWorks: {e}")
        return None

def create_new_part():
    swApp = get_sw_app()
    if not swApp: return "Failed to connect to SolidWorks"
    
    try:
        # swDocPART = 1
        # 8 = swDefaultTemplatePart
        template_path = swApp.GetUserPreferenceStringValue(8)
        
        # NewDocument(TemplateName, PaperSize, Width, Height)
        # Using the default template path if available
        swModel = swApp.NewDocument(template_path, 0, 0, 0)
        if swModel:
            return "New Part created successfully."
        else:
            return "Failed to create new part."
    except Exception as e:
        return f"Error creating part: {e}"

def select_plane(plane_name: str):
    swApp = get_sw_app()
    if not swApp: return "Failed to connect to SolidWorks"
    swModel = swApp.ActiveDoc
    if not swModel: return "No active document open to select a plane on."
    
    plane_name_full = f"{plane_name.capitalize()} Plane"
    if plane_name.lower() == "front":
        plane_name_full = "Front Plane"
    elif plane_name.lower() == "top":
        plane_name_full = "Top Plane"
    elif plane_name.lower() == "right":
        plane_name_full = "Right Plane"
        
    # SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption)
    # pywin32 often fails with Type Mismatch if we pass Python's `None` for a COM object array/pointer.
    # We must explicitly cast it to a VT_DISPATCH variant.
    null_obj = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
    status = swModel.Extension.SelectByID2(plane_name_full, "PLANE", 0.0, 0.0, 0.0, False, 0, null_obj, 0)
    
    if status:
        # Re-orient the camera so the user is looking directly at the selected plane
        swModel.ShowNamedView2("*Normal To", -1)
        swModel.ViewZoomtofit2()
        return f"Selected {plane_name_full}."
    else:
        return f"Failed to select {plane_name_full}."

def start_sketch():
    swApp = get_sw_app()
    if not swApp: return "Failed to connect to SolidWorks"
    swModel = swApp.ActiveDoc
    if not swModel: return "No active document."
    
    swModel.SketchManager.InsertSketch(True)
    return "Sketch started or exited."

def draw_shape(shape_type: str, dimensions: dict):
    swApp = get_sw_app()
    if not swApp: return "Failed to connect to SolidWorks"
    swModel = swApp.ActiveDoc
    if not swModel: return "No active document."
    
    skManager = swModel.SketchManager
    
    shape_type = shape_type.lower()
    try:
        if shape_type == "circle":
            r = float(dimensions.get("radius", 0.05))
            skManager.CreateCircle(0, 0, 0, r, 0, 0)
            swModel.SketchManager.InsertSketch(True)
            swModel.ViewZoomtofit2()
            return f"Drew a circle with radius {r}m"
            
        elif shape_type == "rectangle":
            w = float(dimensions.get("width", 1))
            h = float(dimensions.get("height", 1))
            skManager.CreateCornerRectangle(0, 0, 0, w/2, h/2, 0)
            swModel.SketchManager.InsertSketch(True)
            swModel.ViewZoomtofit2()
            return f"Drew a rectangle {w}m x {h}m"
            
        elif shape_type == "line":
            l = float(dimensions.get("length", 0.1))
            skManager.CreateLine(0, 0, 0, l, 0, 0)
            swModel.SketchManager.InsertSketch(True)
            swModel.ViewZoomtofit2()
            return f"Drew a line of length {l}m"
            
        return f"Shape type '{shape_type}' not supported."
    except Exception as e:
        return f"Error drawing shape: {e}"

def apply_feature(feature_type: str, parameters: dict):
    swApp = get_sw_app()
    if not swApp: return "Failed to connect to SolidWorks"
    swModel = swApp.ActiveDoc
    if not swModel: return "No active document."
    
    featureManager = swModel.FeatureManager
    feature_type = feature_type.lower()
    
    try:
        if feature_type == "extrude_boss":
            depth = float(parameters.get("depth", 2))
            featureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, depth, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
            return f"Applied Extrude Boss with depth {depth}m"
            
        elif feature_type == "cut_extrude":
            depth = float(parameters.get("depth", 2))
            featureManager.FeatureCut3(True, False, False, 0, 0, depth, depth, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)
            return f"Applied Cut Extrude with depth {depth}m"
            
        return f"Feature type '{feature_type}' not implemented."
    except Exception as e:
        return f"Error applying feature: {e}"

def analyze_ui_state():
    """Diagnostic tool to mimic screen reading for specific UI elements."""
    # Since visual AI is handling the heavy lifting visually,
    # we can just return a generic confirmation or read COM properties if needed.
    return "UI State analyzed: Waiting for user to complete the sketch or apply a feature."
    
TOOL_DISPATCHER = {
    "create_new_part": create_new_part,
    "select_plane": select_plane,
    "start_sketch": start_sketch,
    "draw_shape": draw_shape,
    "apply_feature": apply_feature,
    "analyze_ui_state": analyze_ui_state
}

async def execute_tool(name: str, args: dict) -> str:
    """Executes the mapped SolidWorks tool asynchronously so we don't block the WebSocket."""
    func = TOOL_DISPATCHER.get(name)
    if not func:
        return f"Tool '{name}' not found locally."
    
    loop = asyncio.get_event_loop()
    def wrapper():
        # COM requires its own thread initialization
        pythoncom.CoInitialize()
        try:
            if args:
                return func(**args)
            return func()
        finally:
            pythoncom.CoUninitialize()
        
    try:
        result = await loop.run_in_executor(None, wrapper)
        return str(result)
    except Exception as e:
        return f"Error executing tool {name}: {e}"
