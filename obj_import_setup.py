import bpy
import numpy as np
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from mathutils import Matrix
import os

bl_info = {
    "name": "obj_import_setup",
    "author": "Rich Colburn, email: the3dadvantage@gmail.com",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D >  > Tools",
    "description": "Imports obj files and sets up materials and names",
    "warning": "A man is standing right behind you planning to lick you. If you turn around he will vanish.",
    "wiki_url": "",
    "category": '3D View'}


# calback functions ---------------
def oops(self, context):
    # placeholder for reporting errors or other messages
    return


def folder_select():
    print("selecting folder")


def apply_transfrom(ob, use_location=False, use_rotation=False, use_scale=False):
    mb = ob.matrix_basis
    I = Matrix()
    loc, rot, scale = mb.decompose()

    # rotation
    T = Matrix.Translation(loc)
    #R = rot.to_matrix().to_4x4()
    R = mb.to_3x3().normalized().to_4x4()
    S = Matrix.Diagonal(scale).to_4x4()

    transform = [I, I, I]
    basis = [T, R, S]

    def swap(i):
        transform[i], basis[i] = basis[i], transform[i]

    if use_location:
        swap(0)
    if use_rotation:
        swap(1)
    if use_scale:
        swap(2)
        
    M = transform[0] @ transform[1] @ transform[2]
    if hasattr(ob.data, "transform"):
        ob.data.transform(M)
    for c in ob.children:
        c.matrix_local = M @ c.matrix_local
        
    ob.matrix_basis = basis[0] @ basis[1] @ basis[2]


# universal ---------------------
def apply_transforms(ob, co):
    """Get vert coords in world space"""
    m = np.array(ob.matrix_world, dtype=np.float32)
    mat = m[:3, :3].T # rotates backwards without T
    loc = m[:3, 3]
    return co @ mat + loc


def apply_scale():
    for ob in bpy.data.objects:
        if ob.OBS_props.is_imported:    
            apply_transfrom(ob, use_scale=True)



def normal_setup(mat, image, bsdf_node):

    nodes = mat.node_tree.nodes
    node_tex = nodes.new('ShaderNodeTexImage')
    node_tex.image = bpy.data.images.load(image)
    node_tex.location = -600, -1200
    node_tex.image.colorspace_settings.name = "Non-Color"

    bump = bpy.context.scene.OBS_props.use_bump
    links = mat.node_tree.links

    if bump:   
        node_bump = nodes.new('ShaderNodeBump')
        node_bump.inputs[0].default_value = bpy.context.scene.OBS_props.bump_strength
        link = links.new(node_bump.inputs["Height"], node_tex.outputs["Color"])
    else:
        node_bump = nodes.new('ShaderNodeNormalMap')
        link = links.new(node_bump.inputs["Color"], node_tex.outputs["Color"])
    
    node_bump.location = -200, -900

        
    
    link = links.new(node_bump.outputs["Normal"], bsdf_node.inputs["Normal"])


def roughness_setup(mat, image, bsdf_node):
    nodes = mat.node_tree.nodes    
    
    node_tex = nodes.new('ShaderNodeTexImage')
    node_tex.image = bpy.data.images.load(image)
    node_tex.location = -600, -900
    node_tex.image.colorspace_settings.name = "Non-Color"
    
    links = mat.node_tree.links
    link = links.new(node_tex.outputs["Color"], bsdf_node.inputs["Roughness"])



def metallic_setup(mat, image, bsdf_node):
    nodes = mat.node_tree.nodes    
    
    node_tex = nodes.new('ShaderNodeTexImage')
    node_tex.image = bpy.data.images.load(image)
    node_tex.location = -600, -600
    node_tex.image.colorspace_settings.name = "Non-Color"
    
    links = mat.node_tree.links
    link = links.new(node_tex.outputs["Color"], bsdf_node.inputs["Metallic"])


def ao_setup(mat, image, color_node, bsdf_node):
    nodes = mat.node_tree.nodes
    
    
    node_tex = nodes.new('ShaderNodeTexImage')
    node_tex.image = bpy.data.images.load(image)
    node_tex.location = -600, -300
    
    node_mix = nodes.new('ShaderNodeMixRGB')
    node_mix.location = -200, 0
    node_mix.inputs[0].default_value = 1
    node_mix.blend_type = "MULTIPLY"
    
    
    links = mat.node_tree.links
    link = links.new(node_mix.outputs["Color"], bsdf_node.inputs["Base Color"])
    
    link = links.new(node_mix.inputs["Color1"], color_node.outputs["Color"])
    link = links.new(node_mix.inputs["Color2"], node_tex.outputs["Color"])
    
    #link = links.new(node_principled.outputs["BSDF"], node_output.inputs["Surface"])    
    

def material_setup(mat, image):
    nodes = mat.node_tree.nodes
    nodes.clear()

    # Add the Principled Shader node
    node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_principled.location = 0,0

    # Add the Image Texture node
    node_tex = nodes.new('ShaderNodeTexImage')
    # Assign the image
    if image is not None:
        node_tex.image = bpy.data.images.load(image)
    node_tex.location = -600,0

    # Add the Output node
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_output.location = 400,0

    # Link all nodes
    links = mat.node_tree.links
    link = links.new(node_tex.outputs["Color"], node_principled.inputs["Base Color"])
    link = links.new(node_principled.outputs["BSDF"], node_output.inputs["Surface"])
    return node_tex, node_principled
    

def line_up():
    """line up objects on the x axis based on bounds"""
    offset = 0.0
    for ob in bpy.data.objects:
        co = np.empty((len(ob.data.vertices), 3), dtype=np.float32)
        ob.data.vertices.foreach_get("co", co.ravel())
        wco = apply_transforms(ob, co)
        
        x_min = np.min(wco[:, 0])
        x_max = np.max(wco[:, 0])
        
        new_loc = -x_min + offset
        ob.location.x = -x_min + offset
        offset = x_max + new_loc + 1.0
                    
                    
def setup_objects():
    
    path = bpy.context.scene.OBS_props.folder_path
    isDirectory = os.path.isdir(path)
    if not isDirectory:
        path = os.path.dirname(os.path.abspath(path))

    offset = 0.0
    
    obj_names = []
    mats = {}
    
    for f in os.listdir(path):
        file = os.path.join(path, f)
        # checking if it is a file
        if os.path.isfile(file):
            split = file.split(".")
            
            f_type = split[-1].lower()

            if f_type == "obj":
                bobj_name = f.split(".")[0]
                obj_names += [bobj_name]
                
                # For debugging the materials. If the object is already
                #   in the blend file don't import.
                if bobj_name in bpy.data.objects:
                    msg = "skipped imort of: " + bobj_name + " Object already in blend file."
                    bpy.context.window_manager.popup_menu(oops, title=msg, icon='ERROR')
                    ob = bpy.data.objects[bobj_name]
                    base_name = ob.name.split(".")[0]
                else:
                    bpy.ops.import_scene.obj(filepath=file)
                    ob = bpy.context.selected_objects[-1]
                    base_name = ob.name.split(".")[0]
                    ob.asset_mark()
                    ob.OBS_props.is_imported = True

                    co = np.empty((len(ob.data.vertices), 3), dtype=np.float32)
                    ob.data.vertices.foreach_get("co", co.ravel())
                    wco = apply_transforms(ob, co)
                    
                    x_min = np.min(wco[:, 0])
                    x_max = np.max(wco[:, 0])
                    
                    new_loc = -x_min + offset
                    ob.location.x = -x_min + offset
                    offset = x_max + new_loc + 1.0

                mat = ob.material_slots[0].material
                mat.name = base_name
                mat.blend_method = "OPAQUE"
                mats[bobj_name] = mat

    for obn in obj_names:
        mod_obn = obn.lower().replace("_", "")
        images = {}
        base_color_image = None
        ao_image = None
        metallic_image = None
        normal_image = None
        roughness_image = None
        
        for f in os.listdir(path):
            file = os.path.join(path, f)
            # checking if it is a file
            if os.path.isfile(file):
                split = file.split(".")
                
                f_type = split[-1].lower()
                if f_type in ['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'gif', 'exr', 'tga']:
                    
                    base_name = f.split(".")[0]
                    img_name = f.split(".")[0].split("Mat")[0][:-1]
                    mod_name = img_name.lower().replace("_", "")
                    
                    if mod_name.startswith(mod_obn):
                        images[img_name] = file
                        # base color
                        if base_name.lower().endswith(("diffuse", "albedo", "base_color", "basecolor")):
                            base_color_image = file
                        
                        # AO
                        if base_name.lower().endswith(("ao", "ambient_occlusion")):
                            ao_image = file
                        
                        # metallic
                        if base_name.lower().endswith("metallic"):
                            metallic_image = file

                        if base_name.lower().endswith("normal"):
                            normal_image = file

                        if base_name.lower().endswith("roughness"):
                            roughness_image = file

        mat = mats[obn]
                    
        color_node, bsdf_node = material_setup(mat, base_color_image)
        
        if ao_image is not None:
            ao_setup(mat, ao_image, color_node, bsdf_node)

        if metallic_image is not None:
            metallic_setup(mat, metallic_image, bsdf_node)
        
        if roughness_image is not None:
            roughness_setup(mat, roughness_image, bsdf_node)
        
        if normal_image is not None:
            normal_setup(mat, normal_image, bsdf_node)

        # albedo (this is base color probably. Check by using node wrangler)
        # normal
        # roughness
        # ambient_occlusion
        # mixed_ao
        # metallic
        # base_color
        # specular
        # bump (default height. Normal map goes into height, strength is set to 0.2)
        #   add option to use normal map or bump map.
        # 
        # diffuse
        # mix ao and base color. Probably with multiply node.

    
def main():
    running = True
    #running = False
    if running:
        for mat in bpy.data.materials:
            if mat.node_tree:
                for n in mat.node_tree.nodes:
                    if n.type == 'TEX_IMAGE':
                        if n.image is None:
                            print(mat.name,'has an image node with no image')
                            continue
                        if n.image.name[-4] == ".":
                            if n.image.name[-3:].isdigit():
                                name = n.image.name[:-4]
                                exists = False
                                for img in bpy.data.images:
                                    if img.name in name:
                                        exists = True
                                if exists:
                                    n.image = bpy.data.images[name]
                                else:
                                    n.image.name = name

        bpy.ops.outliner.orphans_purge(do_recursive=True)                            



class ObsPropsObject(bpy.types.PropertyGroup):

    is_imported:\
    bpy.props.BoolProperty(name="Is Imported",
        description="For finding the imported objects later",
        default=False)


class ObsPropsScene(bpy.types.PropertyGroup):

    folder_path:\
    bpy.props.StringProperty(name="Folder Path",
        description="Where to find objs and images",
        default="Select Path")

    use_bump:\
    bpy.props.BoolProperty(name="Use Bump",
        description="Bump map instead of normal map",
        default=False)
        
    bump_strength:\
    bpy.props.FloatProperty(name="Bump Strength",
        description="Effect of bump maps",
        default=0.2)


class OT_TestOpenFilebrowser(Operator, ImportHelper):
    bl_idname = "test.open_filebrowser"
    bl_label = "Open the file browser (yay)"
    use_filter_folder = True
    filename_ext = "."
    def execute(self, context):
        """Do something with the selected file(s)."""
        bpy.context.scene.OBS_props.folder_path = self.filepath
        return {'FINISHED'}


class ObsSelectFolder(bpy.types.Operator):
    """Obs Folder Select"""
    bl_idname = "scene.obs_folder_select"
    bl_label = "Obs folder select"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        folder_select()
        return {'FINISHED'}


class ObsObjectSetup(bpy.types.Operator):
    """Obs object setup"""
    bl_idname = "scene.obs_object_setup"
    bl_label = "Obs object setup"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        setup_objects()
        return {'FINISHED'}
    

class ObsApplyScale(bpy.types.Operator):
    """Obs Apply Scale"""
    bl_idname = "scene.obs_apply_scale"
    bl_label = "Obs apply scale"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        apply_scale()
        return {'FINISHED'}    


class ObsLineUpObjects(bpy.types.Operator):
    """Obs Line Up Objects"""
    bl_idname = "scene.obs_line_up_objects"
    bl_label = "Obs line up objects"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        line_up()
        return {'FINISHED'}


class PANEL_PT_objImportSetupMain(bpy.types.Panel):
    """Obs Panel Main"""
    bl_label = "Ons Main"
    bl_idname = "PANEL_PT_Obs_setup_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Obj Setup"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        #col.operator("scene.obs_folder_select", text="Folder Select", icon='FILE_FOLDER')
        col.operator("test.open_filebrowser", text="Browse", icon='FILE_FOLDER')
        #col.operator("example.select_dir", text="Dir", icon='FILE_FOLDER')
        col.prop(bpy.context.scene.OBS_props, "folder_path", text="Path", icon='FILE_FOLDER')
        col.prop(bpy.context.scene.OBS_props, "use_bump", text="Use Bump", icon='NORMALS_FACE')
        col.prop(bpy.context.scene.OBS_props, "bump_strength", text="Bump Distance", icon='SMOOTHCURVE')
        col.operator("scene.obs_object_setup", text= "Import/Setup", icon='IMPORT')
        col.operator("scene.obs_apply_scale", text= "Apply Scale", icon='CHECKMARK')
        col.operator("scene.obs_line_up_objects", text= "Line Up ", icon='TRACKING_FORWARDS_SINGLE')


#===============================
class SelectDirExample(bpy.types.Operator):

    """Create render for all chracters"""
    bl_idname = "example.select_dir"
    bl_label = "Dir Selection Example Operator"
    bl_options = {'REGISTER'}

    # Define this to tell 'fileselect_add' that we want a directoy
    directory = bpy.props.StringProperty(
        name="Outdir Path",
        description="Where I will save my stuff"
        # subtype='DIR_PATH' is not needed to specify the selection mode.
        # But this will be anyway a directory path.
        )

    def execute(self, context):
        
        bpy.context.scene.OBS_props.folder_path = self.directory
        print("Selected dir: ")# + self.directory + "'")

        return {'FINISHED'}

    def invoke(self, context, event):
        # Open browser, take reference to 'self' read the path to selected
        # file, put path in predetermined self fields.
        # See: https://docs.blender.org/api/current/bpy.types.WindowManager.html#bpy.types.WindowManager.fileselect_add
        context.window_manager.fileselect_add(self)
        # Tells Blender to hang on for the slow user input
        return {'RUNNING_MODAL'}

#===============================


classes = (
    PANEL_PT_objImportSetupMain,
    ObsSelectFolder,
    ObsObjectSetup,
    ObsPropsScene,
    ObsPropsObject,
    OT_TestOpenFilebrowser,
    SelectDirExample,
    ObsApplyScale,
    ObsLineUpObjects,
)


def register():
    # classes
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.OBS_props = bpy.props.PointerProperty(type=ObsPropsScene)
    bpy.types.Object.OBS_props = bpy.props.PointerProperty(type=ObsPropsObject)


def unregister():
    # classes

    msg = "I guess you don't love me anymore. Goodbye cruel world. I die!"
    bpy.context.window_manager.popup_menu(oops, title=msg, icon='GHOST_ENABLED')

    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()
