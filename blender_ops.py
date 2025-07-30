# coding: utf-8
# blender_ops.py

import bpy
import os
import numpy as np
import mathutils

# Import config module to access global project settings
import config
import utils

# --- Utility Functions ---

def setup_blender_environment():
    """
    Configura l'ambiente Blender, attivando la GPU (CUDA) se specificato nel config.
    """
    print("\n--- Setting up Blender Environment ---")
    bpy.context.scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons["cycles"].preferences

    if config.BLENDER_DEVICE.upper() == 'GPU':
        # Forza l'uso di CUDA, dato che l'ambiente e' ottimizzato per NVIDIA.
        prefs.compute_device_type = 'CUDA'
        bpy.context.scene.cycles.device = 'GPU'
        
        # Abilita tutti i dispositivi CUDA disponibili
        prefs.get_devices()
        for device in prefs.devices:
            if device.type == 'CUDA':
                device.use = True
                print(f"  Enabled CUDA device: {device.name}")
    else:
        # Ripiega sulla CPU se non e' richiesta la GPU
        prefs.compute_device_type = 'NONE'
        bpy.context.scene.cycles.device = 'CPU'

    print(f"  Blender render engine set to CYCLES and device to {bpy.context.scene.cycles.device}.")

def clear_blender_scene():
    """Clears all objects from the Blender scene."""
    print("Clearing Blender scene...")
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    print("Blender scene cleared.")

def get_all_mesh_objects():
    """Returns a list of all mesh objects in the current Blender scene."""
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

# --- Import and Export Functions ---

def import_stl_file(filepath, new_name):
    bpy.ops.wm.stl_import(filepath=filepath) # Blender 4.5
    # bpy.ops.import_mesh.stl(filepath=filepath) # Blender 4.2 (fallback)
    if bpy.context.selected_objects:
        obj = bpy.context.selected_objects[0]
        return rename_imported_objects(obj, new_name)
    return []

def import_obj_file(filepath, new_name):
    bpy.ops.wm.obj_import(filepath=filepath) # Blender 4.5
    # bpy.ops.import_scene.obj(filepath=filepath) # Blender 4.2 (fallback)
    if bpy.context.selected_objects:
        return rename_imported_objects(list(bpy.context.selected_objects), new_name)
    return []

def import_fbx_file(filepath, new_name):
    bpy.ops.wm.fbx_import(filepath=filepath) # Blender 4.5
    # bpy.ops.import_scene.fbx(filepath=filepath) # Blender 4.2 (fallback)
    if bpy.context.selected_objects:
        return rename_imported_objects(list(bpy.context.selected_objects), new_name)
    return []

def import_glb_file(filepath, new_name):
    bpy.ops.import_scene.gltf(filepath=filepath) # 4.2 Format
    if bpy.context.selected_objects:
        return rename_imported_objects(list(bpy.context.selected_objects), new_name)
    return []

def export_glb(filepath, root_object_to_export):
    """Exports the specified root object and its children to GLB format."""
    bpy.ops.object.select_all(action='DESELECT') # Deselect all first

    if root_object_to_export:
        # Select the root object and all its children recursively
        root_object_to_export.select_set(True)
        for child in root_object_to_export.children_recursive:
            child.select_set(True)
        bpy.context.view_layer.objects.active = root_object_to_export # Set active object for export
    else:
        print("Warning: No root object provided for GLB export. Exporting all scene objects.")
        bpy.ops.object.select_all(action='SELECT') # Export all if no specific objects are given

    selected_count = len(bpy.context.selected_objects)
    print(f"  Exporting {selected_count} objects to GLB: {filepath}")
    bpy.ops.export_scene.gltf(filepath=filepath, export_extras=True, use_selection=True) # Always use selection if root is provided
    print(f"Exported GLB: {filepath}")
    bpy.ops.object.select_all(action='DESELECT')

def export_fbx(filepath, objects_to_export):
    """
    Exports the specified objects and their children to FBX format.
    """
    bpy.ops.object.select_all(action='DESELECT')

    if not objects_to_export:
        print("Warning: No objects provided for FBX export. Exporting all scene objects.")
        bpy.ops.object.select_all(action='SELECT')
    else:
        for obj in objects_to_export:
            obj.select_set(True)
            for child in obj.children_recursive:
                child.select_set(True)
        if objects_to_export:
            bpy.context.view_layer.objects.active = objects_to_export[0]

    selected_count = len(bpy.context.selected_objects)
    print(f"  Exporting {selected_count} objects to FBX: {filepath}")
    
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
        use_armature_deform_only=True,
        bake_anim=False
    )
    print(f"Exported FBX: {filepath}")
    bpy.ops.object.select_all(action='DESELECT')

def save_blender_scene(output_dir, filename):
    """Saves the current Blender scene to a .blend file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"  Created directory for blend file: {output_dir}")

    filepath = os.path.join(output_dir, filename)
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    print(f"  Blender scene saved to: {filepath}")

def rename_imported_objects(imported_objs, new_name):
    """Helper function to rename imported objects, handling single or multiple."""
    renamed_objects = []
    if isinstance(imported_objs, list):
        for obj in imported_objs:
            obj.name = new_name
            renamed_objects.append(obj)
    elif imported_objs:
        imported_objs.name = new_name
        renamed_objects.append(imported_objs)
    return renamed_objects

def import_meshes_into_blender_scene(input_folder_path):
    """
    Imports STL mesh files from the specified folder.
    Imports all .stl files found in the directory.
    """
    imported_objects = []
    print("\n--- Phase: Automatic File Import ---")

    if not os.path.exists(input_folder_path):
        print(f"  Input folder not found: {input_folder_path}. No meshes to import.")
        return []

    for filename in os.listdir(input_folder_path):
        filepath = os.path.join(input_folder_path, filename)
        name_without_ext = os.path.splitext(filename)[0]
        file_extension = os.path.splitext(filename)[1].lower()

        if not os.path.isfile(filepath):
            continue # Skip directories or other non-file entries

        imported_this_file = []
        if file_extension == '.stl':
            imported_this_file = import_stl_file(filepath, name_without_ext)
        else:
            print(f"  Unsupported file type for '{filename}': {file_extension}. Skipping (only .stl is supported).")
            continue
        
        if imported_this_file:
            imported_objects.extend(imported_this_file)
            print(f"  Imported '{filename}' as '{name_without_ext}' (Type: {file_extension.upper()}).")
        else:
            print(f"  Failed to import '{filename}'.")
            
    if not imported_objects:
        print(f"  No .stl meshes found in '{input_folder_path}'.")
    return imported_objects

def apply_world_scale(mesh_objects, scale_factor):
    """
    Applies a uniform scale factor to all specified mesh objects and
    then applies the scale transformation to make it permanent.
    """
    print(f"\n--- Phase: Applying World Scale Factor ({scale_factor}) ---")
    
    if not mesh_objects:
        print("  No mesh objects to scale. Skipping.")
        return

    for obj in mesh_objects:
        if obj.type == 'MESH':
            # Set the scale
            obj.scale = (scale_factor, scale_factor, scale_factor)
            # print(f"  Set scale of '{obj.name}' to {obj.scale}.")

    # Select all mesh
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        if obj.type == 'MESH':
            obj.select_set(True)
    
    # Apply the scale to all mesh objects at once
    if bpy.context.selected_objects:
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        print(f"  Applied scale transformation to {len(bpy.context.selected_objects)} selected mesh objects.")
    
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.update()

# --- Cleaning Functions ---

def merge_vertices_by_distance(mesh_objects, distance):
    """Merges vertices in mesh objects within a given distance."""
    print(f"Performing 'Merge by Distance' for mesh objects with distance: {distance}")
    if distance > 0:
        for obj in mesh_objects:
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)

                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=distance)
                bpy.ops.object.mode_set(mode='OBJECT')
                obj.select_set(False)
                # print(f"  Merge vertices on '{obj.name}' completed.")
        bpy.context.view_layer.update()

def fix_normal_orientation(mesh_objects):
    """Recalculates normals to point outside for mesh objects."""
    print("Performing 'Fix Normal Orientation' (Recalculate Outside) for mesh objects.")
    for obj in mesh_objects:
        if obj.type == 'MESH':
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            obj.select_set(False)
            # print(f"  Normals orientation of '{obj.name}' corrected.")
    bpy.context.view_layer.update()

def delete_small_features(mesh_objects, threshold):
    """Deletes degenerate geometry (small features) from mesh objects."""
    print("Performing 'Delete Small Features' (Dissolve Degenerate) for mesh objects.")
    if threshold > 0:
        for obj in mesh_objects:
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_degenerate(threshold=config.DISSOLVE_DEGENERATE_THRESHOLD)
                bpy.ops.object.mode_set(mode='OBJECT')
                obj.select_set(False)
                # print(f"  Small features of '{obj.name}' deleted.")
        bpy.context.view_layer.update()

def decimate_mesh_objects(mesh_objects, max_faces_limit, segment_manifest):
    """Decimates mesh objects to reduce face count taking account of the export_as_individual_mesh in segmentMappings."""

    print(f"Performing 'Decimation' for mesh objects with limit: {max_faces_limit} / ({max_faces_limit*1000} on individual object) faces.")
    for obj in mesh_objects:
        decimate = False
        polycount = 0
        poly_removed = 0

        if obj.name in segment_manifest:
            export_details = segment_manifest[obj.name].get('custom_parameters', {})
            export = export_details.get('export_as_individual_mesh')
            if not export or len(obj.data.polygons)>max_faces_limit*1000: # upper limit to prevent crash
                decimate = True
                current_faces = len(obj.data.polygons)
                polycount += current_faces
                print(f"'{obj.name}' is flagged Export as Individual, decimation skipped. Faces: '{current_faces}'.")

        if obj.type == 'MESH' and decimate:
            current_faces = len(obj.data.polygons)
            polycount += current_faces
            print(f"  Object '{obj.name}': {current_faces} faces.")

            if current_faces > max_faces_limit:
                ratio = max_faces_limit / current_faces
                print(f"  Reduction needed for '{obj.name}'. Ratio: {ratio:.4f}")

                mod = obj.modifiers.new(name="DecimateMod", type='DECIMATE')
                mod.decimate_type = 'COLLAPSE'
                mod.ratio = ratio

                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode='OBJECT')
                
                bpy.ops.object.modifier_apply(modifier=mod.name)
                obj.select_set(False)
                
                new_faces = len(obj.data.polygons)
                poly_removed += new_faces
                print(f"  Decimation on '{obj.name}' completed. New faces: {new_faces}.")
            else:
                print(f"  Decimation not needed for '{obj.name}'. Faces: {current_faces}.")
                polycount += current_faces
    bpy.context.view_layer.update()
    return polycount, poly_removed

def OLD_decimate_mesh_objects(mesh_objects, max_faces_limit):
    """Decimates mesh objects to reduce face count."""
    print(f"Performing 'Decimation' for mesh objects with limit: {max_faces_limit} faces per object.")
    for obj in mesh_objects:
        if obj.type == 'MESH':
            current_faces = len(obj.data.polygons)
            print(f"  Object '{obj.name}': {current_faces} current faces.")

            if current_faces > max_faces_limit:
                ratio = max_faces_limit / current_faces
                print(f"  Reduction needed for '{obj.name}'. Ratio: {ratio:.4f}")

                mod = obj.modifiers.new(name="DecimateMod", type='DECIMATE')
                mod.decimate_type = 'COLLAPSE'
                mod.ratio = ratio

                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode='OBJECT')
                
                bpy.ops.object.modifier_apply(modifier=mod.name)
                obj.select_set(False)
                
                new_faces = len(obj.data.polygons)
                print(f"  Decimation on '{obj.name}' completed. New faces: {new_faces}.")
            else:
                print(f"  Decimation not needed for '{obj.name}'. Current faces: {current_faces}.")
    bpy.context.view_layer.update()

def apply_smoothing_normals(mesh_objects, method='WEIGHTED', average_type='CORNER_ANGLE'):
    """Applies smoothing to normals of mesh objects."""
    print(f"\n--- Phase: Applying Normal Smoothing ({method}) ---")
    for obj in mesh_objects:
        if obj.type != 'MESH':
            print(f"  Skipping '{obj.name}': non e' un oggetto mesh.")
            continue

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        if method == 'WEIGHTED':
            if "WeightedNormalsMod" in obj.modifiers:
                obj.modifiers.remove(obj.modifiers["WeightedNormalsMod"])
                print(f"  Removed existing WeightedNormalsMod from '{obj.name}'.")

            mod = obj.modifiers.new(name="WeightedNormalsMod", type='WEIGHTED_NORMAL')
            mod.keep_sharp = True

            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.ops.object.shade_smooth()
            #print(f"  Applied Weighted Normals and Shade Smooth to '{obj.name}'.")

        elif method == 'AVERAGE':
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.average_normals(average_type=average_type)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.shade_smooth()
            #print(f"  Normals of '{obj.name}' averaged ({average_type}) and Shade Smooth applied.")
        else:
            print(f"  Smoothing method '{method}' not recognized. Skipping for '{obj.name}'.")
        
        obj.select_set(False)
    bpy.context.view_layer.update()

def apply_all_modifiers(mesh_objects):
    """Applies all modifiers on the given mesh objects."""
    print("\n--- Phase: Applying All Modifiers ---")
    for obj in mesh_objects:
        if obj.type != 'MESH':
            print(f"  Skipping '{obj.name}': non e' un oggetto mesh.")
            continue

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        # Apply all modifiers one by one
        # Iterate over a copy of the modifiers list, as applying them removes them from the original list
        for modifier in list(obj.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                print(f"  Applied modifier '{modifier.name}' to '{obj.name}'.")
            except RuntimeError as e:
                print(f"  Warning: Could not apply modifier '{modifier.name}' to '{obj.name}': {e}")
        obj.select_set(False)
    bpy.context.view_layer.update()

def create_single_scene_root(mesh_objects, root_name_base):
    """
    Calculates the geometric center of all mesh_objects, creates a Root empty at that center,
    parents all meshes to it, and then moves the Root to the world origin (0,0,0).
    This centers the entire group while preserving relative positions.
    Returns the created root object.
    """
    print("\n--- Phase: Centering Scene and Creating Hierarchy ---")

    if not mesh_objects:
        print("  No mesh objects provided to center. Skipping.")
        return None

    # 1. Calculate the combined bounding box of all mesh objects in world space
    min_coord = mathutils.Vector((float('inf'), float('inf'), float('inf')))
    max_coord = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))

    for obj in mesh_objects:
        if obj.type == 'MESH':
            # obj.bound_box gives 8 corners in local space. Transform them to world space.
            world_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
            for corner in world_corners:
                min_coord.x = min(min_coord.x, corner.x)
                min_coord.y = min(min_coord.y, corner.y)
                min_coord.z = min(min_coord.z, corner.z)
                max_coord.x = max(max_coord.x, corner.x)
                max_coord.y = max(max_coord.y, corner.y)
                max_coord.z = max(max_coord.z, corner.z)

    # 2. Calculate the center of the combined bounding box
    if min_coord.x == float('inf'):
        print("  Could not determine bounding box. Using world origin as center.")
        bounding_box_center = mathutils.Vector((0.0, 0.0, 0.0))
    else:
        bounding_box_center = (min_coord + max_coord) / 2.0
    print(f"  Calculated geometric center of all meshes: {bounding_box_center}")

    # 3. Create the single root empty object at the calculated center
    root_name = f"{root_name_base}_Root"
    bpy.ops.object.select_all(action='DESELECT')
    root_object = bpy.data.objects.get(root_name)
    if not root_object:
        bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=bounding_box_center)
        root_object = bpy.context.active_object
        root_object.name = root_name
        print(f"  Created single Root object: '{root_object.name}' at calculated center.")
    else:
        root_object.location = bounding_box_center
        print(f"  Root object '{root_object.name}' already exists. Location updated to calculated center.")

    # 4. Parent all mesh objects to this single root
    for obj in mesh_objects:
        if obj.type == 'MESH':
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='OBJECT')
            
            if obj.parent:
                obj.parent = None # Clear existing parent

            obj.parent = root_object
            obj.matrix_parent_inverse = root_object.matrix_world.inverted()
            # print(f"  '{obj.name}' parented to '{root_object.name}'.")

    # 5. Move the Root (and all its children) to the world origin
    root_object.location = config.ROOT_WORLD_POSITION
    print(f"  Moved Root '{root_object.name}' to world origin (0,0,0), centering the group.")

    bpy.context.view_layer.update()
    return root_object


# --- Material Application Functions ---

def match_materials_on_manifest(segments_manifest, blender_shader_registry):
    """
    Enriches the segment manifest with Blender-specific material data.
    This function contains all the fallback logic for deciding which material to use.
    """
    print("\n--- Matching Manifest with Material Data ---")
    shader_ref_map = blender_shader_registry.get('shader_ref', {})
    category_shader_map = blender_shader_registry.get('biological_categories', {})
    default_shader_ref = "default_shader"
    direct_match_count = 0
    partial_match_count = 0
    snomed_match_count = 0
    biological_category_match_count= 0
    fallback_match_count = 0


    for seg_name, seg_data in segments_manifest.items():
        shader_ref_to_use = None # Resettato per ogni segmento
        biological_category_type = seg_data.get('custom_parameters', {}).get('biological_category')
        snomed_type = seg_data.get('snomed_details', {}).get('type')

        # 1. Direct Match Logic: Check for a shader named after the segment itself
        potential_direct_match = f"{seg_name.lower()}_shader"
        if potential_direct_match in shader_ref_map:
            shader_ref_to_use = potential_direct_match
            print(f"DEBUG: Segment '{seg_name}' -> Direct Match: '{shader_ref_to_use}'.")
            direct_match_count += 1
        
        # 1.5 Partial Match Logic
        if shader_ref_to_use is None:
            partial_matches = [
                shader_key for shader_key in shader_ref_map 
                if any(part in shader_key.lower() for part in seg_name.lower().split('_'))
            ]
            if partial_matches:
                shader_ref_to_use = partial_matches[0]
                print(f"DEBUG: Segment '{seg_name}' -> Partial Match: '{shader_ref_to_use}'.")
                partial_match_count += 1

        # 2. SNOMED Type Match Logic (Medium-High Priority)
        if shader_ref_to_use is None and snomed_type:
            # potential_snomed_match = f"{snomed_type.capitalize()}"
            potential_snomed_match = f"{snomed_type.lower()}_shader"
            # potential_snomed_match = f"{snomed_type}_shader"
            if potential_snomed_match in shader_ref_map:
                shader_ref_to_use = potential_snomed_match
                print(f"DEBUG: Segment '{seg_name}' -> SNOMED Type Match: '{potential_snomed_match}'.")
                snomed_match_count += 1

        # 3. Biological Category Match Logic
        if shader_ref_to_use is None and biological_category_type:
            if biological_category_type in category_shader_map:
                shader_ref_to_use = category_shader_map[biological_category_type]
                print(f"DEBUG: Segment '{seg_name}' -> Biological Category Match: '{shader_ref_to_use}'.")
                biological_category_match_count += 1
            
        # 4. Fallback to Default
        if shader_ref_to_use is None:
            shader_ref_to_use = default_shader_ref
            fallback_match_count += 1

        # Get material details from the chosen shader_ref
        shader_details = shader_ref_map.get(shader_ref_to_use, {})
        seg_data['custom_parameters']['shader_ref'] = shader_ref_to_use
        seg_data['custom_parameters']['blend_file'] = shader_details.get('blend_file')
        seg_data['custom_parameters']['blend_material'] = shader_details.get('blend_material')
        seg_data['custom_parameters']['color_override'] = shader_details.get('color_override')
        
        # print(f"DEBUG: Segment '{seg_name}' -> Shader Ref '{shader_ref_to_use}' -> Material '{shader_details.get('blend_material')}' -> Color Override '{shader_details.get('color_override')}'.")
    print(f"DEBUG: *** RECAP Match count. Direct: '{direct_match_count}', Partial: '{partial_match_count}, 'Snomed: '{snomed_match_count}', Biological Category: '{biological_category_match_count}', Fallback: '{fallback_match_count}'  ")
    return segments_manifest

def apply_materials_from_manifest(imported_meshes, enriched_manifest):
    """
    Applies materials to meshes based on the pre-enriched manifest.
    This function is a simple executor, with no decision logic.
    Returns a list of temporary items (nodes and objects) to be cleaned up later.
    """
    print("\n--- Applying Materials from Enriched Manifest ---")
    materials_to_append = {}  # {mat_name: blend_file_path}
    temp_items_for_cleanup = [] # List to track created override nodes AND projector objects

    # First, determine which object corresponds to which entry in the manifest
    # and gather all unique materials that need to be appended.
    for obj in imported_meshes:
        # The object name should match a key in the manifest.
        # This includes individual segments and combined meshes.
        obj_name_in_manifest = obj.name
        
        if obj_name_in_manifest in enriched_manifest:
            mat_details = enriched_manifest[obj_name_in_manifest].get('custom_parameters', {})
            mat_name = mat_details.get('blend_material')
            blend_file = mat_details.get('blend_file')

            if mat_name and blend_file:
                if mat_name not in materials_to_append:
                    materials_to_append[mat_name] = os.path.join(config.SHADERS_DIR, blend_file)
                # Store the final material name directly on the object for the next step
                obj['material_to_assign'] = mat_name
            else:
                print(f"  WARNING: Material details missing for '{obj_name_in_manifest}' in manifest.")
        else:
            print(f"  WARNING: Object '{obj.name}' not found in manifest. Cannot assign material.")

    # --- Append all unique materials in one go ---
    for mat_name, blend_path in materials_to_append.items():
        if mat_name and mat_name not in bpy.data.materials:
            try:
                bpy.ops.wm.append(
                    filepath=os.path.join(blend_path, 'Material', mat_name),
                    directory=os.path.join(blend_path, 'Material'),
                    filename=mat_name
                )
                print(f"  Appended material '{mat_name}' from '{os.path.basename(blend_path)}'.")

                # --- Add TEMPLATE MATERIALS to cleanup list ---
                temp_items_for_cleanup.append(mat_name) #Material
                print(f"    -> found Template Material '{mat_name}', scheduled for cleanup.")
                # # Ispeziona i nodi del materiale appena importato
                # mat_nodes = bpy.data.materials.get(mat_name)
                # if mat_nodes and mat_nodes.use_nodes:
                #     for node in mat_nodes.node_tree.nodes:
                #         temp_items_for_cleanup.append(node.name)
                #         print(f"      -> Found Template Material Node '{node.name}' in template '{mat_name}', scheduled for cleanup.")

                # --- Add PROJECTOR to cleanup LIST ---
                projector_name = f"{mat_name.capitalize()}_projector"
                if projector_name in bpy.data.objects:
                    temp_items_for_cleanup.append(projector_name)
                    print(f"    -> Found Projector '{projector_name}', scheduled for cleanup.")
                

            except Exception as e:
                print(f"  ERROR appending material '{mat_name}': {e}")

    # --- Apply the assigned material to each object ---
    for obj in imported_meshes:
        mat_name = obj.get('material_to_assign')
        if mat_name:
            base_material = bpy.data.materials.get(mat_name)
            if base_material:
                # Create a unique copy of the material for this object
                new_mat = base_material.copy()
                new_mat.name = f"{obj.name}_{mat_name}" # e.g., "spleen_organ_2_mat"
                
                # Assign the new, unique material to the object
                if obj.data.materials:
                    obj.data.materials[0] = new_mat
                else:
                    obj.data.materials.append(new_mat)
                print(f"  Applied unique material '{new_mat.name}' (copy of '{mat_name}') to '{obj.name}'.")

                # --- Apply Color Override if specified ---
                if obj.name in enriched_manifest:
                    mat_details = enriched_manifest[obj.name].get('custom_parameters', {})
                    color_override_hex = mat_details.get('color_override')

                    if color_override_hex:
                        #print ("\n**** COLOR OVERRIDE ROUTINE ***\n")
                        mix_node_name = apply_color_override_node(obj, new_mat, color_override_hex)
                        if mix_node_name:
                            temp_items_for_cleanup.append(mix_node_name)
                # --- End Color Override ---
            else:
                print(f"  ERROR: Base material '{mat_name}' not found after append for object '{obj.name}'.")
    return temp_items_for_cleanup


def apply_color_override_node(obj, material, color_override_hex):
    """
    Applies a color override to the material of an object by adding a Mix node.
    """
    print(f"  Applying color override '{color_override_hex}' to '{obj.name}'.")
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    
    principled_bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if principled_bsdf and 'Base Color' in principled_bsdf.inputs:
        base_color_input = principled_bsdf.inputs['Base Color']
        
        if base_color_input.links:
            original_from_node = base_color_input.links[0].from_node
            original_from_socket = base_color_input.links[0].from_socket

            # Crea il NUOVO nodo Mix (ShaderNodeMix)
            mix_node = nodes.new('ShaderNodeMix')
            mix_node.name = f"{obj.name}_ColorOverrideMix"
            mix_node.label = "Color Override Mix"
            mix_node.data_type = 'RGBA' # Fondamentale: specifica che lavora con colori
            mix_node.blend_type = 'MULTIPLY'
            mix_node.inputs['Factor'].default_value = 1.0
            
            mix_node.location = original_from_node.location + mathutils.Vector((300, 0))
            
            override_rgb = utils.hex_to_rgb(color_override_hex)
            # print(f"    DEBUG: override_rgb (from hex_to_rgb): {override_rgb}")

            
            # LINK 'A'
            links.new(original_from_socket, mix_node.inputs['A'])
                                
            # INPUT 'B'
            mix_node.inputs['B'].default_value = (*override_rgb, 1.0)
            
            for link in list(base_color_input.links):
                links.remove(link)
            # OUTPUT 'Result'
            links.new(mix_node.outputs['Result'], base_color_input)
            print(f"    Applied Mix node override for '{obj.name}'.")
            return mix_node.name
        else:
            print(f"    Applying color override directly to Base Color for '{obj.name}' (no existing link).")
            principled_bsdf.inputs['Base Color'].default_value = (*utils.hex_to_rgb(color_override_hex), 1.0)
            return None
    else:
        print(f"    WARNING: Principled BSDF or 'Base Color' input not found for '{obj.name}'. Cannot apply color override.")
        return None

# --- Bake Functions ---

def uv_map(mesh_objects, texture_size):
    print("\n--- Phase: UV Mapping ---")
    for obj in mesh_objects:
        if not obj or obj.type != 'MESH':
            print(f"Object '{obj.name}' not found or not a mesh. Skipping UV Map.")
            continue

        print(f"  Creating/Updating UV Map for '{obj.name}'...")
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)

        # Remove all existing UV layers to recreate from scratch
        while obj.data.uv_layers:
            obj.data.uv_layers.remove(obj.data.uv_layers[0])
        print(f"  Removed all existing UV maps for '{obj.name}'.")

        uv_map_name = "UVMap"
        new_uv_layer = obj.data.uv_layers.new(name=uv_map_name)
        print(f"  Created new UV map '{uv_map_name}' for '{obj.name}'.")
        
        new_uv_layer.active = True
        new_uv_layer.active_render = True

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        # Smart UV Project parameters: angle_limit, island_margin, area_weight, correct_aspect, scale_to_bounds
        bpy.ops.uv.smart_project(angle_limit=60.0, island_margin=0.02, area_weight=0.75, correct_aspect=True, scale_to_bounds=True)
        
        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(False)
        print(f"  UV map for '{obj.name}' created/updated with Smart UV Project.")
    bpy.context.view_layer.update()

def bake_channel(mesh_object, channel_type, textures_dir, texture_size, color_space):
    """Generic function to bake a specific channel (Color, Normal, Roughness, etc.)."""
    obj_name = mesh_object.name
    print(f"Baking {channel_type.capitalize()} for '{obj_name}'...")
    obj = mesh_object
    
    if not obj or obj.type != 'MESH' or not obj.data.materials:
        print(f"Object '{obj_name}' not found, is not a mesh, or has no materials. Skipping bake.")
        return False
    
    # Select the mesh
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Get mesh material
    mat = obj.data.materials[0] # Assumes material is at index 0
    mat.use_nodes = True
    nodes = mat.node_tree.nodes

    # Create texture node for the bake
    image_name = f"{obj_name}_{channel_type.lower()}"
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.name = image_name # Assegna un nome specifico basato sull'oggetto e sul canale
    print(f"DEBUG:  Created Image Texture Node '{tex_node.name}' for bake.")

    # Determine if the image should have an alpha channel (Diffuse channel use alpha as transparency)
    create_alpha = False
    if channel_type.lower() == 'diffuse':
        create_alpha = True

    # Create or reuse (in case of multiple bake) image data
    image = bpy.data.images.get(image_name)
    if not image:
        image = bpy.data.images.new(name=image_name, width=texture_size, height=texture_size, alpha=create_alpha)
        print(f"  Created new image data '{image_name}'.")
    else:
        # If image exists, ensure its size matches
        if image.size[0] != texture_size or image.size[1] != texture_size:
            image.scale(texture_size, texture_size)
            print(f"  Resized existing image '{image_name}' to {texture_size}x{texture_size}.")
        print(f"  Reusing existing image data '{image_name}'.")

    image.colorspace_settings.name = color_space
    tex_node.image = image # Assign the image to the node

    # Select Texture node...
    nodes.active = tex_node
    tex_node.select = True

    # ...in Object mode
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    
    bake_args = {
        'type': channel_type.upper(),
        'target': 'IMAGE_TEXTURES',
        'width': texture_size,
        'height': texture_size,
        'margin': 8, # Margine dilazione
    }

    # Adjust bake arguments for each bake type
    if channel_type.upper() == 'NORMAL':
        bake_args['normal_space'] = 'TANGENT'
        bake_args['normal_r'] = 'POS_X'
        bake_args['normal_g'] = 'POS_Y'
        bake_args['normal_b'] = 'POS_Z'
    elif channel_type.upper() == 'DIFFUSE':
        bake_args['pass_filter'] = {'COLOR'}


    print(f"  Performing {channel_type.lower()} bake for '{obj_name}'...")
    bpy.ops.object.bake(**bake_args) 
    
    # Save the image with the correct path
    image.filepath_raw = os.path.join(textures_dir, f"{obj_name}_{channel_type.lower()}.png")
    image.file_format = 'PNG'
    image.save()
    print(f"  Baked {channel_type.capitalize()} saved to {image.filepath_raw}")
    
    # Deselect the image node for subsequent bakes
    obj.select_set(False)
    tex_node.select = False
    return tex_node.name

def bake_textures(imported_meshes, textures_dir, texture_size, blender_device):
    """Orchestrates baking of Color, Normal, and Roughness textures for all meshes."""
    created_bake_nodes = []

    for obj in imported_meshes:
        if obj.type != 'MESH':
            continue # Skip non-mesh objects

        # Bake Albedo (Diffuse)
        node= bake_channel(obj, 'diffuse', textures_dir, texture_size, 'sRGB') # 'diffuse' for albedo
        if node:
            created_bake_nodes.append(node)

        # Bake Normal
        node= bake_channel(obj, 'normal', textures_dir, texture_size, 'Non-Color')
        if node: 
            created_bake_nodes.append(node)
        # Bake Roughness
        node= bake_channel(obj, 'roughness', textures_dir, texture_size, 'Non-Color')
        if node:
            created_bake_nodes.append(node)
    return created_bake_nodes

def TO_DO_NEW_remove_bake_temp_items(cleanup_registry):
    print("\n--- Phase: Structured Cleanup ---")
    count = 0

    # NODES
    for mat_name, node_name in cleanup_registry.get("nodes", []):
        mat = bpy.data.materials.get(mat_name)
        if mat and mat.use_nodes:
            node = mat.node_tree.nodes.get(node_name)
            if node:
                try:
                    mat.node_tree.nodes.remove(node)
                    print(f"  Removed node '{node_name}' from material '{mat_name}'.")
                    count += 1
                except Exception as e:
                    print(f"  Error removing node '{node_name}' from '{mat_name}': {e}")

    # OBJECTS
    for obj_name in cleanup_registry.get("objects", []):
        obj = bpy.data.objects.get(obj_name)
        if obj:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                print(f"  Removed object '{obj_name}'")
                count += 1
            except Exception as e:
                print(f"  Error removing object '{obj_name}': {e}")

    # MATERIALS
    for mat_name in cleanup_registry.get("materials", []):
        mat = bpy.data.materials.get(mat_name)
        if mat:
            try:
                bpy.data.materials.remove(mat, do_unlink=True)
                print(f"  Removed material '{mat_name}'")
                count += 1
            except Exception as e:
                print(f"  Error removing material '{mat_name}': {e}")

    print(f"  Total {count} temporary items removed.")

def remove_bake_temp_nodes(item_names_to_remove):
    """
    Removes temporary items (shader nodes AND scene objects) from the scene
    based on a list of their names. The name is kept for documentation consistency.
    This version is hardened against iteration errors.
    """
    print("\n--- Phase: Cleaning Up Temporary Items (Nodes and Objects) ---")
    if not item_names_to_remove:
        print("  No temporary items to clean up.")
        return

    items_removed_count = 0
    
    # Create set of names to avoid redundant checks
    node_targets = []     # list of (material_name, node_name)
    names_to_remove_set = set(item_names_to_remove)

    # 1. Clean up Shader Nodes from all materials
    for mat in bpy.data.materials:
        if mat.use_nodes:
            nodes = mat.node_tree.nodes
            # Iterate over a copy of the node names to safely remove them
            for node_name in list(names_to_remove_set):
                if node_name in nodes:
                    try:
                        node_to_remove = nodes[node_name]
                        nodes.remove(node_to_remove)
                        print(f"  Removed temporary node '{node_name}' from material '{mat.name}'.")
                        items_removed_count += 1
                    except Exception as e:
                        print(f"  Error removing node '{node_name}' from material '{mat.name}': {e}")

    # 2. Clean up Scene Objects
    # Iterate over a copy of the object names to safely remove them
    for obj_name in list(names_to_remove_set):
        if obj_name in bpy.data.objects:
            try:
                object_to_remove = bpy.data.objects[obj_name]
                bpy.data.objects.remove(object_to_remove, do_unlink=True)
                print(f"  Removed temporary object: '{obj_name}'")
                items_removed_count += 1
            except Exception as e:
                print(f"  Error removing object '{obj_name}': {e}")

    # 3. Clean up Materials
    for mat_name in list(names_to_remove_set):
        if mat_name in bpy.data.materials:
            try:
                material_to_remove = bpy.data.materials[mat_name]
                bpy.data.materials.remove(material_to_remove, do_unlink=True)
                print(f"  Removed temporary material: '{mat_name}'")
                items_removed_count += 1
            except Exception as e:
                print(f"  Error removing material '{mat_name}': {e}")

    print(f"  Total {items_removed_count} temporary items removed.")
    bpy.context.view_layer.update()


def link_baked_textures(imported_meshes, textures_dir):
    """Links baked textures to the Principled BSDF node in the material of each mesh."""
    print("\n--- Phase: Linking Baked Texture Nodes (PBR Standard for GLB/General) ---")
    
    # Lista per raccogliere i nodi temporanei creati da questa funzione
    # (es. Normal Map Node) che dovranno essere puliti alla fine.
    nodes_created_by_linking = [] 

    for obj in imported_meshes:
        if not obj or not obj.data.materials:
            continue
        
        mat = obj.data.materials[0] # Assumes material is at index 0
        if not mat or not mat.use_nodes:
            continue
            
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        principled_bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not principled_bsdf:
            print(f"  Principled BSDF node not found in material of '{obj.name}'. Skipping linking.")
            continue

        # --- IMPORTANT: REUSE EXISTING NODES INSTEAD OF CREATING NEW ONES ---

        # 1. Albedo (Diffuse)
        # Search for the node created during bake_channel
        albedo_image_node = nodes.get(f"{obj.name}_diffuse") 
        if albedo_image_node and albedo_image_node.image: # Ensure node exists and has an image
            # No need to load image again, it's already assigned during bake
            albedo_image_node.label = "Baked Albedo"
            albedo_image_node.location = (-800, 300) # Re-position as needed
            albedo_image_node.interpolation = 'Linear' # Ensure interpolation is set
            albedo_image_node.image.colorspace_settings.name = 'sRGB' # Ensure colorspace is set
            
            if 'Base Color' in principled_bsdf.inputs:
                for link in principled_bsdf.inputs['Base Color'].links: links.remove(link)
                links.new(albedo_image_node.outputs['Color'], principled_bsdf.inputs['Base Color'])
                print(f"  Linked Albedo map to Principled BSDF for '{obj.name}'.")
            else:
                print(f"  Warning: Principled BSDF has no 'Base Color' input for '{obj.name}'.")
        else:
            print(f"  Baked Albedo node/image not found for '{obj.name}'. Skipping Albedo linking.")

        # 2. Normal
        normal_image_node = nodes.get(f"{obj.name}_normal")
        if normal_image_node and normal_image_node.image:
            normal_image_node.label = "Baked Normal"
            normal_image_node.location = (-800, 0)
            normal_image_node.interpolation = 'Linear'
            normal_image_node.image.colorspace_settings.name = 'Non-Color' 
            
            normal_map_node = nodes.new('ShaderNodeNormalMap') # This is a new node, needs to be tracked
            normal_map_node.label = "Normal Map"
            normal_map_node.name = f"{obj.name}_NormalMapNode"
            normal_map_node.location = (-600, 0)
            nodes_created_by_linking.append(normal_map_node.name) # Track this node for later removal
            
            links.new(normal_image_node.outputs['Color'], normal_map_node.inputs['Color'])
            if 'Normal' in principled_bsdf.inputs:
                for link in principled_bsdf.inputs['Normal'].links: links.remove(link)
                links.new(normal_map_node.outputs['Normal'], principled_bsdf.inputs['Normal'])
                print(f"  Linked Normal map to Principled BSDF for '{obj.name}'.")
            else:
                print(f"  Warning: Principled BSDF has no 'Normal' input for '{obj.name}'.")
        else:
            print(f"  Baked Normal node/image not found for '{obj.name}'. Skipping Normal linking.")

        # 3. Roughness
        roughness_image_node = nodes.get(f"{obj.name}_roughness")
        if roughness_image_node and roughness_image_node.image:
            roughness_image_node.label = "Baked Roughness"
            roughness_image_node.location = (-800, -300)
            roughness_image_node.interpolation = 'Linear'
            roughness_image_node.image.colorspace_settings.name = 'Non-Color' 
            
            if 'Roughness' in principled_bsdf.inputs:
                for link in principled_bsdf.inputs['Roughness'].links: links.remove(link)
                links.new(roughness_image_node.outputs['Color'], principled_bsdf.inputs['Roughness'])
                print(f"  Linked Roughness map to Principled BSDF for '{obj.name}'.")
            else:
                print(f"  Warning: Principled BSDF has no 'Roughness' input for '{obj.name}'.")
        else:
            print(f"  Baked Roughness node/image not found for '{obj.name}'. Skipping Roughness linking.")

        # 4. Metallic (for PBR Adobe workflow, from create_base_metalness_map)
        # Assuming create_base_metalness_map creates a new image and names it obj.name_metallic
        metallic_image_node = nodes.get(f"{obj.name}_metallic") 
        if metallic_image_node and metallic_image_node.image:
            metallic_image_node.label = "Baked Metallic"
            metallic_image_node.location = (-800, -600)
            metallic_image_node.interpolation = 'Linear'
            metallic_image_node.image.colorspace_settings.name = 'Non-Color'
            
            if 'Metallic' in principled_bsdf.inputs:
                for link in principled_bsdf.inputs['Metallic'].links: links.remove(link)
                links.new(metallic_image_node.outputs['Color'], principled_bsdf.inputs['Metallic'])
                print(f"  Linked Metallic map to Principled BSDF for '{obj.name}'.")
            else:
                print(f"  Warning: Principled BSDF has no 'Metallic' input for '{obj.name}'.")
        else:
            print(f"  Baked Metallic node/image not found for '{obj.name}'. Skipping Metallic linking.")

    bpy.context.view_layer.update()
    return nodes_created_by_linking # Return any new nodes created by this function

def create_base_metalness_map(mesh_objects, textures_dir, texture_size):
    """
    Creates a base Metalness map (metallic.png) for PBR Adobe workflow
    from the green channel of the baked Roughness map.
    The green channel of the roughness map is replicated across R, G, B channels.
    """
    print("\n--- Phase: Creating Base Metalness Map (for PBR Adobe workflow) ---")
    for obj in mesh_objects:
        obj_name = obj.name
        roughness_path = os.path.join(textures_dir, f"{obj_name}_roughness.png")
        metallic_output_path = os.path.join(textures_dir, f"{obj_name}_metallic.png")

        if not os.path.exists(roughness_path):
            print(f"  Roughness texture missing for {obj_name} at {roughness_path}. Skipping base metalness creation.")
            continue

        metallic_name = f"{obj_name}_metallic"
        if metallic_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[metallic_name], do_unlink=True)
            print(f"  Removed existing base metalness image '{metallic_name}'.")

        roughness_img = bpy.data.images.load(roughness_path)
        
        metallic_img = bpy.data.images.new(
            name=metallic_name,
            width=texture_size,
            height=texture_size,
            alpha=False # Metalness is typically RGB, no alpha
        )
        metallic_img.colorspace_settings.name = 'Non-Color' # Important for data

        print(f"  Processing base metalness texture for {obj_name}...")
        
        if len(roughness_img.pixels) != texture_size * texture_size * 4:
            print(f"  Error: Unexpected pixel count for roughness image {obj_name}. Expected {texture_size * texture_size * 4}, got {len(roughness_img.pixels)}. Cannot create base metalness map.")
            bpy.data.images.remove(roughness_img) # Clean up
            continue

        #Initialize with 4 channels (RGBA) and explicitly set alpha to 1.0
        base_metalness_pixels = np.zeros((texture_size, texture_size, 4)) 
        pixels_from_roughness = np.array(list(roughness_img.pixels)).reshape((texture_size, texture_size, 4)) # Reshape to (H, W, RGBA)
        
        # Replicate green channel of roughness to R, G, B of metalness
        base_metalness_pixels[:,:,0] = pixels_from_roughness[:,:,1] # Red from Roughness Green
        base_metalness_pixels[:,:,1] = pixels_from_roughness[:,:,1] # Green from Roughness Green
        base_metalness_pixels[:,:,2] = pixels_from_roughness[:,:,1] # Blue from Roughness Green
        base_metalness_pixels[:,:,3] = 1.0 # Set Alpha to 1.0 (fully opaque)

        metallic_img.pixels = base_metalness_pixels.ravel().tolist()
        
        metallic_img.filepath_raw = metallic_output_path
        metallic_img.file_format = 'PNG'
        metallic_img.save()
        
        # Clean up the loaded roughness image from Blender's memory if no longer needed
        bpy.data.images.remove(roughness_img, do_unlink=True)
        print(f"  Created base metalness texture for {obj_name} at {metallic_output_path}")

def create_metallic_smoothness_map(mesh_objects, textures_dir, texture_size):
    """
    Creates a combined MetallicSmoothness map for Unity (Universal Render Pipeline - URP)
    from the baked Roughness map.
    Unity URP MetallicSmoothness Map:
    - R channel: Metalness (from G of original Roughness)
    - G channel: Occlusion (set to 0.0 or from separate AO bake)
    - B channel: Detail Mask (set to 0.0)
    - A channel: Smoothness (1 - Roughness, from G of original Roughness)
    """
    print("\n--- Phase: Creating MetallicSmoothness Map for Unity ---")
    for obj in mesh_objects:
        obj_name = obj.name
        roughness_path = os.path.join(textures_dir, f"{obj_name}_roughness.png")
        metallic_smoothness_output_path = os.path.join(textures_dir, f"{obj_name}_MetallicSmoothness.png")

        if not os.path.exists(roughness_path):
            print(f"  Roughness texture missing for {obj_name} at {roughness_path}. Skipping MetallicSmoothness creation.")
            continue

        metallic_smoothness_name = f"{obj_name}_MetallicSmoothness"
        if metallic_smoothness_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[metallic_smoothness_name], do_unlink=True)
            print(f"  Removed existing MetallicSmoothness image '{metallic_smoothness_name}'.")

        roughness_img = bpy.data.images.load(roughness_path)
        
        metallic_smoothness_img = bpy.data.images.new(
            name=metallic_smoothness_name,
            width=texture_size,
            height=texture_size,
            alpha=True # Required for alpha channel
        )
        metallic_smoothness_img.colorspace_settings.name = 'Non-Color'

        print(f"  Processing MetallicSmoothness texture for {obj_name}...")
        
        # Ensure roughness_img.pixels is flat before reshaping
        # Check the number of channels (RGBA = 4)
        if len(roughness_img.pixels) != texture_size * texture_size * 4:
            print(f"  Error: Unexpected pixel count for roughness image {obj_name}. Expected {texture_size * texture_size * 4}, got {len(roughness_img.pixels)}. Cannot create MetallicSmoothness map.")
            bpy.data.images.remove(roughness_img) # Clean up
            continue

        pixels = np.array(list(roughness_img.pixels)).reshape((texture_size, texture_size, 4)) # Reshape to (H, W, RGBA)
        
        metallic_smoothness_pixels = np.zeros_like(pixels) # Initialize with zeros, preserving shape
        
        # R (Metallic): From Green channel of original Roughness map (assuming it contains metalness)
        # For biological models, metalness is often 0.0. Adjust as per your material definition.
        metallic_smoothness_pixels[:,:,0] = pixels[:,:,1] # Copy Green channel to Red

        # G (Occlusion): Set to 0.0 (or from separate AO bake if available)
        metallic_smoothness_pixels[:,:,1] = 0.0 
        
        # B (Detail Mask): Set to 0.0
        metallic_smoothness_pixels[:,:,2] = 0.0 
        
        # A (Smoothness): 1 - (Green channel of original Roughness)
        metallic_smoothness_pixels[:,:,3] = 1.0 - pixels[:,:,1] 

        # Flatten the array back to a 1D list for Blender
        metallic_smoothness_img.pixels = metallic_smoothness_pixels.ravel().tolist()
        
        metallic_smoothness_img.filepath_raw = metallic_smoothness_output_path
        metallic_smoothness_img.file_format = 'PNG'
        metallic_smoothness_img.save()
        
        # Clean up the loaded roughness image from Blender's memory if no longer needed
        bpy.data.images.remove(roughness_img, do_unlink=True)
        print(f"  Created MetallicSmoothness texture for {obj_name} at {metallic_smoothness_output_path}")

def update_shader_nodes_for_unity_export(imported_meshes, textures_dir):
    """
    Updates material nodes to use the combined MetallicSmoothness texture for Unity export consistency.
    This function should be called AFTER create_metallic_smoothness_map.
    Returns a list of all *new* nodes created by this function (MetallicSmoothness, Invert).
    """
    print("\n--- Phase: Updating Shader Nodes for Unity (Metallic/Smoothness) ---")
    
    # Lista per raccogliere i nodi temporanei creati da questa funzione
    nodes_created_by_unity_export_setup = []

    for obj in imported_meshes:
        obj_name = obj.name
        if not obj or not obj.data.materials:
            print(f"Object '{obj_name}' not found or has no materials. Skipping shader update.")
            continue
            
        mat = obj.data.materials[0] # Assumes material is at index 0
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        mat.use_nodes = True # Ensure nodes are enabled
        principled_bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not principled_bsdf:
            print(f"  Principled BSDF node not found in material of '{obj.name}'. Cannot link MetallicSmoothness.")
            continue

        # Remove old Roughness and Metallic links if present
        if 'Roughness' in principled_bsdf.inputs:
            for link in principled_bsdf.inputs['Roughness'].links: links.remove(link)
            print(f"  Removed old Roughness link for '{obj.name}'.")
        if 'Metallic' in principled_bsdf.inputs:
            for link in principled_bsdf.inputs['Metallic'].links: links.remove(link)
            print(f"  Removed old Metallic link for '{obj.name}'.")

        # # Remove the old roughness and metallic image nodes if present
        # # This is good. It cleans up nodes that link_baked_textures might have set up.
        # roughness_node_name = f"{obj_name}_roughness" # This is the name used by bake_channel
        # metallic_node_name = f"{obj_name}_metallic" # This is the name used by create_base_metalness_map
        
        # if roughness_node_name in nodes:
        #     nodes.remove(nodes[roughness_node_name])
        #     print(f"  Removed old roughness node '{roughness_node_name}' for '{obj.name}'.")
        # if metallic_node_name in nodes: # Corrected from metallic_old_node_name
        #     nodes.remove(nodes[metallic_node_name])
        #     print(f"  Removed old metallic node '{metallic_node_name}' for '{obj.name}'.")

        # Load the MetallicSmoothness image
        metallic_smoothness_path = os.path.join(textures_dir, f"{obj_name}_MetallicSmoothness.png")
        if not os.path.exists(metallic_smoothness_path):
            print(f"  MetallicSmoothness texture missing for {obj_name} at {metallic_smoothness_path}. Skipping linking.")
            continue

        metallic_smoothness_img = bpy.data.images.load(metallic_smoothness_path)
        metallic_smoothness_img.colorspace_settings.name = 'Non-Color' 
        
        metallic_smoothness_node_name = f"{obj_name}_MetallicSmoothness_map" # Descriptive name
        metallic_smoothness_node = nodes.get(metallic_smoothness_node_name)
        if not metallic_smoothness_node:
            metallic_smoothness_node = nodes.new('ShaderNodeTexImage')
            metallic_smoothness_node.name = metallic_smoothness_node_name
            metallic_smoothness_node.image = metallic_smoothness_img
            metallic_smoothness_node.location = (-800, -500)
            metallic_smoothness_node.interpolation = 'Linear'
            print(f"  Created new MetallicSmoothness node '{metallic_smoothness_node_name}' for '{obj.name}'.")
        else:
            metallic_smoothness_node.image = metallic_smoothness_img # Ensure it points to the correct image
            print(f"  MetallicSmoothness node '{metallic_smoothness_node_name}' already exists for '{obj.name}'.")
        
        nodes_created_by_unity_export_setup.append(metallic_smoothness_node.name) # Track this node

        # Link Color output (R channel for Metalness) to Principled BSDF Metallic input
        if 'Metallic' in principled_bsdf.inputs:
            for link in principled_bsdf.inputs['Metallic'].links: links.remove(link)
            links.new(metallic_smoothness_node.outputs['Color'], principled_bsdf.inputs['Metallic'])    
            print(f"  Linked Metallic (R channel from MetallicSmoothness) map to Principled BSDF 'Metallic' for '{obj.name}'.")
        else:
            print(f"  Warning: Principled BSDF has no 'Metallic' input for '{obj.name}'.")

        # Link Alpha output (Smoothness) to Principled BSDF Roughness input (inverted to Roughness)
        if 'Roughness' in principled_bsdf.inputs:
            for link in principled_bsdf.inputs['Roughness'].links: links.remove(link)
            invert_node = nodes.new('ShaderNodeInvert') # This is a new node, needs to be tracked
            invert_node.location = metallic_smoothness_node.location + mathutils.Vector((200, -100))
            nodes_created_by_unity_export_setup.append(invert_node.name) # Track this node
            
            links.new(metallic_smoothness_node.outputs['Alpha'], invert_node.inputs['Color'])
            links.new(invert_node.outputs['Color'], principled_bsdf.inputs['Roughness'])
            print(f"  Linked Smoothness (A from MetallicSmoothness, then inverted to Roughness) map to Principled BSDF 'Roughness' for '{obj.name}'.")
        else:
            print(f"  Warning: Principled BSDF has no 'Roughness' input for '{obj.name}'.")
            
    bpy.context.view_layer.update()
    return nodes_created_by_unity_export_setup # Return new nodes for cleanup