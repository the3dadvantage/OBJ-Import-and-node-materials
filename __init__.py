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

if "bpy" in locals():
    import imp
    imp.reload(obj_import_setup)
    print("Reloaded obj_import_setup")
else:
    from . import obj_import_setup
    print("Imported obj_import_setup")

   
def register():
    obj_import_setup.register()

    
def unregister():
    obj_import_setup.unregister()
