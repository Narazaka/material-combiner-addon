# MIT License

# Copyright (c) 2018 shotariya

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import bpy
import os
import time
import random
import pathlib
from . Packer import Packer
from . PIL import Image

class L(list):
    def __new__(self, *args, **kwargs):
        return super(L, self).__new__(self, args, kwargs)

    def __init__(self, *args, **kwargs):
        if len(args) == 1 and hasattr(args[0], '__iter__'):
            list.__init__(self, args[0])
        else:
            list.__init__(self, args)
        self.__dict__.update(kwargs)

    def __call__(self, **kwargs):
        self.__dict__.update(kwargs)
        return self


class GenMat(bpy.types.Operator):
    bl_idname = 'shotariya.gen_mat'
    bl_label = 'Combine materials'
    bl_description = 'Combine selected materials'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bpy.context.mode == 'OBJECT'

    def apply_modifier(self, context):
        for obj in bpy.data.objects:
            if 'ミラー' in obj.modifiers:
                self.report({'INFO'}, obj.name + ' apply')
                Func_Apply_Modifier(self, context, target_object = obj, target_modifiers = ['ミラー'])

    def delete_objects(self, context):
        if context.scene.combine_mode == 'single':
            bpy.data.objects.remove(context.scene.objects['メガネレンズ'])
        else:
            deletes = []
            for obj in context.scene.objects:
                if obj.name.endswith('裏面'):
                    deletes.append(obj)
            for obj in deletes:
                bpy.data.objects.remove(obj)

    def join_objects(self, context):
        if context.scene.combine_mode == 'single':
            for obj in context.scene.objects:
                if obj.type == 'MESH' and obj.name != 'メガネレンズ':
                    obj.select = True
                else:
                    obj.select = False
        elif context.scene.combine_mode == 'multi3':
            for obj in context.scene.objects:
                if obj.type != 'MESH' or obj.name.endswith('裏面'):
                    obj.select = False
                else:
                    obj.select = True
        else:
            select_objs = ['口', '耳', '顔', '眼球', '頬', '口リップシンク回避用']
            for obj in context.scene.objects:
                if obj.name in select_objs:
                    obj.select = True
                else:
                    obj.select = False
        context.scene.objects.active = context.scene.objects['顔']
        bpy.ops.object.join()
        if context.scene.combine_mode == 'obj_only':
            select_objs = ['メガネ', 'メガネレンズ']
            for obj in context.scene.objects:
                if obj.name in select_objs:
                    obj.select = True
                else:
                    obj.select = False
            context.scene.objects.active = context.scene.objects['メガネ']
            bpy.ops.object.join()
            select_objs = ['アホ毛', '髪・リボン']
            for obj in context.scene.objects:
                if obj.name in select_objs:
                    obj.select = True
                else:
                    obj.select = False
            context.scene.objects.active = context.scene.objects['髪・リボン']
            bpy.ops.object.join()

    def execute(self, context):
        self.apply_modifier(context)
        self.report({'INFO'}, 'all:{}'.format([obj.name for obj in context.scene.objects]))
        # single = 1マテリアル＆1オブジェクト
        # multi = マテリアルを体と服に統合＆最低限のオブジェクト統合のみ
        # multi3 = マテリアルを体と服に統合＆1オブジェクト
        # only_obj = 最低限のオブジェクト統合のみ
        if context.scene.combine_mode == 'single':
            self.execute_core(context, context.scene.objects, '結合', (1024, 1024))
        elif context.scene.combine_mode == 'multi' or context.scene.combine_mode == 'multi3':
            body_object_names = ['アホ毛', '髪・リボン', '髪・リボン裏面', '体', '耳', 'NOTIFY-FRONT', 'EMOTE']
            self.execute_core(context, [obj for obj in context.scene.objects if obj.name in body_object_names], '結合_体', (1024, 1024))
            face_object_names = ['口', '眼球', '顔', '頬', '口リップシンク回避用'] # 顔はもともと1テクスチャ
            # self.execute_core(context, [obj for obj in context.scene.objects if obj.name in body_object_names], 'combined_face', (256, 256))
            self.execute_core(context, [obj for obj in context.scene.objects if obj.name not in body_object_names and obj.name not in face_object_names], '結合_服', (512, 512))

        self.delete_objects(context)
        self.join_objects(context)

        return{'FINISHED'}

    def execute_core(self, context, objects, texture_name, size, prefix_dir = None):
        self.report({'INFO'}, 'combine->{}'.format(texture_name))
        start_time = time.time()
        files = []
        broken_materials = []
        copies = {}
        standard_mats = {}
        broken_links = []
        indexes = []
        scn = context.scene
        save_path = scn.combined_path
        unique_id = str(random.randrange(9999999999))
        if not save_path:
            self.report({'ERROR'}, 'Please select Folder for Combined Texture')
            return {'FINISHED'}
        bpy.ops.shotariya.uv_fixer()
        for obj in objects:
            if obj.type == 'MESH':
                if not obj.data.uv_layers.active or obj.hide:
                    continue
                for mat_slot in obj.material_slots:
                    if mat_slot:
                        mat = mat_slot.material
                        mat_index = 0
                        for index in range(len(obj.material_slots)):
                            if obj.material_slots[index].material == mat:
                                mat_index = index
                        if mat.to_combine:
                            width = 0
                            height = 0
                            for face in obj.data.polygons:
                                if face.material_index == mat_index:
                                    if len(face.loop_indices) > 0:
                                        face_coords = [obj.data.uv_layers.active.data[loop_idx].uv for loop_idx in
                                                       face.loop_indices]
                                        max_width = max([z.x for z in face_coords])
                                        max_height = max([z.y for z in face_coords])
                                        if max_width > width:
                                            width = max_width
                                        if max_height > height:
                                            height = max_height
                            if (width > 1) or (height > 1):
                                broken_materials.append(mat.name)
        if broken_materials:
            broken_materials = ',\n    '.join([', '.join(broken_materials[x:x + 5])
                                               for x in range(0, len(broken_materials), 5)])
            self.report({'ERROR'}, 'Following materials has UV bounds greater than 1:\n    {}\n\n'
                                   'Use these tools to fix:\n'
                                   '    • Save textures by UVs\n'
                                   '    • Pack UVs by splitting mesh\n'.format(broken_materials))
            return {'FINISHED'}
        for obj in objects:
            if obj.type == 'MESH':
                if not obj.data.uv_layers.active or obj.hide:
                    continue
                for mat_slot in obj.material_slots:
                    if mat_slot:
                        mat = mat_slot.material
                        if mat.to_combine:
                            tex_slot = False
                            for j in range(len(mat.texture_slots)):
                                if mat.texture_slots[j]:
                                    if mat.texture_slots[j].texture:
                                        if mat.use_textures[j]:
                                            tex_slot = mat.texture_slots[j]
                                            break
                            if tex_slot:
                                tex = tex_slot.texture
                                if tex.image:
                                    image_path = bpy.path.abspath(tex.image.filepath)
                                    if len(image_path.split(os.sep)[-1].split('.')) > 1:
                                        if image_path not in files:
                                            files.append(image_path)
                                            standard_mats[mat] = image_path
                                        else:
                                            for s_mat, s_path in standard_mats.items():
                                                if s_path == image_path:
                                                    if s_mat in copies:
                                                        copies[s_mat].append(mat)
                                                    else:
                                                        copies[s_mat] = [mat]
                            else:
                                diffuse = L(int(mat.diffuse_color.r * 255),
                                            int(mat.diffuse_color.g * 255),
                                            int(mat.diffuse_color.b * 255))
                                diffuse.size = (8, 8)
                                diffuse.name = mat.name
                                files.append(diffuse)
        for x in files:
            if not isinstance(x, (list,)):
                path = pathlib.Path(x)
                if not path.is_file():
                    broken_links.append(x.split(os.sep)[-1])
                    files.remove(x)
        combined_copies = 0
        if len(files) < 2:
            if copies:
                for obj in objects:
                    if obj.type == 'MESH':
                        if not obj.data.uv_layers.active or obj.hide:
                            continue
                        scn.objects.active = obj
                        for m_mat, cs_mat in copies.items():
                            for c_mat in cs_mat:
                                if m_mat.mat_index == c_mat.mat_index:
                                    if (m_mat.name in obj.data.materials) and (c_mat.name in obj.data.materials):
                                        if m_mat.name != c_mat.name:
                                            combined_copies += 1
                                            to_delete = obj.data.materials.find(c_mat.name)
                                            for face in obj.data.polygons:
                                                if face.material_index == to_delete:
                                                    face.material_index = obj.data.materials.find(m_mat.name)
                                            context.object.active_material_index = to_delete
                                            bpy.ops.object.material_slot_remove()
                if combined_copies > 0:
                    bpy.ops.shotariya.list_actions(action='GENERATE_MAT')
                    bpy.ops.shotariya.list_actions(action='GENERATE_TEX')
                    self.report({'INFO'}, 'Copies were combined')
                    return {'FINISHED'}
            self.report({'ERROR'}, 'Nothing to Combine {}'.format(files))
            return {'FINISHED'}
        images = sorted([{'w': i.size[0], 'h': i.size[1], 'path': path, 'img': i}
                         for path, i in ((x, Image.open(x).convert('RGBA')) if not isinstance(x, (list,))
                                         else (x.name, x) for x in files)],
                        key=lambda x: min([x['w'], x['h']]), reverse=True)
        packer = Packer.Packer(images)
        images = packer.fit()
        width = max([img['fit']['x'] + img['w'] for img in images])
        height = max([img['fit']['y'] + img['h'] for img in images])
        if any(size) > 20000:
            self.report({'ERROR'}, 'Output Image Size way too big')
            return {'FINISHED'}
        image = Image.new('RGBA', size)
        for img in images:
            if img['fit']:
                if isinstance(img['img'], (list,)):
                    img['img'] = (img['img'][0], img['img'][1], img['img'][2])
                image.paste(img['img'], (img['fit']['x'],
                                         img['fit']['y'],
                                         img['fit']['x'] + img['w'],
                                         img['fit']['y'] + img['h']))
        for obj in objects:
            if obj.type == 'MESH':
                if not obj.data.uv_layers.active or obj.hide:
                    continue
                scn.objects.active = obj
                mat_len = len(obj.material_slots)
                mats = []
                new_mats = []
                for mat_slot in obj.material_slots:
                    if mat_slot:
                        mat = mat_slot.material
                        if mat:
                            if mat.to_combine:
                                mat_name = texture_name
                                if mat_name not in obj.data.materials:
                                    if mat_name not in bpy.data.materials:
                                        material = bpy.data.materials.new(name=mat_name)
                                        indexes.append(mat.mat_index)
                                        tex_name = texture_name
                                        if tex_name not in bpy.data.textures:
                                            texture = bpy.data.textures.new(tex_name, 'IMAGE')
                                        else:
                                            texture = bpy.data.textures[tex_name]
                                        slot = material.texture_slots.add()
                                        slot.texture = texture
                                    else:
                                        material = bpy.data.materials[mat_name]
                                    if material not in new_mats:
                                        new_mats.append(material)
                for materials in new_mats:
                    obj.data.materials.append(materials)
                for img in images:
                    for i in range(mat_len):
                        mat = obj.material_slots[i].material
                        mat_name = texture_name
                        tex_slot = False
                        for j in range(len(mat.texture_slots)):
                            if mat.texture_slots[j]:
                                if mat.texture_slots[j].texture:
                                    if mat.use_textures[j]:
                                        tex_slot = mat.texture_slots[j]
                                        break
                        if tex_slot:
                            tex = tex_slot.texture
                            if tex.image:
                                texture_path = bpy.path.abspath(tex.image.filepath)
                                if texture_path == img['path']:
                                    for face in obj.data.polygons:
                                        if face.material_index == i:
                                            if len(face.loop_indices) > 0:
                                                face_coords = [obj.data.uv_layers.active.data[loop_idx].uv for loop_idx in
                                                               face.loop_indices]
                                                for z in face_coords:
                                                    reset_x = z.x * (img['w'] - 2) / size[0]
                                                    reset_y = 1 + z.y * (img['h'] - 2) / size[1] - img['h'] / size[1]
                                                    z.x = reset_x + (img['fit']['x'] + 1) / size[0]
                                                    z.y = reset_y - (img['fit']['y'] - 1) / size[1]
                                                face.material_index = obj.data.materials.find(mat_name)
                                    if mat.name not in mats:
                                        mats.append(mat.name)
                        else:
                            if mat.to_combine:
                                if img['path'] == mat.name:
                                    for face in obj.data.polygons:
                                        if face.material_index == i:
                                            if len(face.loop_indices) > 0:
                                                face_coords = [obj.data.uv_layers.active.data[loop_idx].uv for loop_idx in
                                                               face.loop_indices]
                                                for z in face_coords:
                                                    reset_x = z.x * (img['w'] - 2) / size[0]
                                                    reset_y = 1 + z.y * (img['h'] - 2) / size[1] - img['h'] / size[1]
                                                    z.x = reset_x + (img['fit']['x'] + 1) / size[0]
                                                    z.y = reset_y - (img['fit']['y'] - 1) / size[1]
                                                face.material_index = obj.data.materials.find(mat_name)
                                    if mat.name not in mats:
                                        mats.append(mat.name)
                for mater in mats:
                    context.object.active_material_index = [x.material.name for x in
                                                            context.object.material_slots].index(mater)
                    bpy.ops.object.material_slot_remove()
        final_image_path = os.path.join(save_path, 'Textures', prefix_dir, texture_name + '.png') if prefix_dir else os.path.join(save_path, 'Textures', texture_name + '.png')
        image.save(final_image_path)
        for index in indexes:
            mat = bpy.data.materials[texture_name]
            mat.mat_index = index
            mat.use_shadeless = True
            mat.alpha = 0
            mat.use_transparency = True
            mat.texture_slots[0].use_map_alpha = True
            tex = mat.texture_slots[0].texture
            tex.image = bpy.data.images.load(final_image_path)
        for mesh in bpy.data.meshes:
            mesh.show_double_sided = True
        bpy.ops.shotariya.list_actions(action='GENERATE_MAT')
        bpy.ops.shotariya.list_actions(action='GENERATE_TEX')
        print('{} seconds passed'.format(time.time() - start_time))
        if broken_links:
            broken_links = ',\n    '.join([', '.join(broken_links[x:x + 5])
                                           for x in range(0, len(broken_links), 5)])
            self.report({'ERROR'}, 'Materials were combined\nFiles not found:\n    {}'.format(broken_links))
            return {'FINISHED'}
        self.report({'INFO'}, 'Materials were combined.')
        return{'FINISHED'}





# Apply Modifier https://sites.google.com/site/matosus304blendernotes/home/download#apply_modifier

#Copyright (c) 2014 mato.sus304(mato.sus304@gmail.com)
#
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

######################################################
def Clear_Shape_Keys(Name):
    obj = bpy.context.active_object
    if obj.data.shape_keys == None:
        return True

    obj.active_shape_key_index = len(obj.data.shape_keys.key_blocks)-1
    while len(obj.data.shape_keys.key_blocks)>1:
        #print(obj.data.shape_keys.key_blocks[obj.active_shape_key_index])

        if obj.data.shape_keys.key_blocks[obj.active_shape_key_index].name == Name:
            obj.active_shape_key_index = 0
            #print(Name)
        else:
            bpy.ops.object.shape_key_remove()

    bpy.ops.object.shape_key_remove()

def Clone_Object(Obj):
    tmp_obj = Obj.copy()
    tmp_obj.name = "applymodifier_tmp_%s"%(Obj.name)
    tmp_obj.data = tmp_obj.data.copy()
    tmp_obj.data.name = "applymodifier_tmp_%s"%(Obj.data.name)
    bpy.context.scene.objects.link(tmp_obj)
    return tmp_obj

def Delete_Object(Obj):
    if Obj.data.users == 1:
        Obj.data.user_clear()
    for scn in bpy.data.scenes:
        try:
            bpy.context.scene.objects.unlink(Obj)
        except:
            pass

######################################################

def Func_Apply_Modifier(self, context, target_object = None, target_modifiers = None):
    if target_object == None:
        obj_src = bpy.context.active_object
    else:
        obj_src = target_object

    if len(obj_src.modifiers) == 0:
        self.report({'INFO'}, obj_src.name + ' skip no mod')
        #if object has no modifier then skip
        return True

    #make single user
    if obj_src.data.users != 1:
        obj_src.data = obj_src.data.copy()

    if obj_src.data.shape_keys == None: # ここなおした
        #if object has no shapekeys, just apply modifier
        bpy.context.scene.objects.active = obj_src
        for x in target_modifiers:
            try:
                bpy.ops.object.modifier_apply(modifier=x)
            except RuntimeError:
                pass
        return True

    obj_fin = Clone_Object(obj_src)

    bpy.context.scene.objects.active = obj_fin
    Clear_Shape_Keys('Basis')

    if target_modifiers == None:
        target_modifiers = []
        for x in obj_fin.modifiers:
            if x.show_viewport:
                target_modifiers.append(x.name)

    for x in target_modifiers:
        try:
            bpy.ops.object.modifier_apply(modifier=x)
        except RuntimeError:
            pass

    flag_onError = False
    list_skipped = []

    for i in range(1, len(obj_src.data.shape_keys.key_blocks)):
        tmp_name = obj_src.data.shape_keys.key_blocks[i].name
        obj_tmp = Clone_Object(obj_src)

        bpy.context.scene.objects.active = obj_tmp
        Clear_Shape_Keys(tmp_name)

        for x in target_modifiers:
            try:
                bpy.ops.object.modifier_apply(modifier=x)
            except RuntimeError:
                pass

        obj_tmp.select = True
        bpy.context.scene.objects.active = obj_fin
        try:
            bpy.ops.object.join_shapes()
            obj_fin.data.shape_keys.key_blocks[-1].name = tmp_name
        except:
            flag_onError = True
            list_skipped.append(tmp_name)


        Delete_Object(obj_tmp)

    if flag_onError:
        def draw(self, context):
            self.layout.label("Vertex Count Disagreement! Some shapekeys skipped.")
            for s in list_skipped:
                self.layout.label(s)

        bpy.context.window_manager.popup_menu(draw, title="Error", icon='INFO')

        return False

    tmp_name = obj_src.name
    tmp_data_name = obj_src.data.name
    obj_fin.name = tmp_name + '.tmp'


    obj_src.data = obj_fin.data
    obj_src.data.name = tmp_data_name

    for x in target_modifiers:
        obj_src.modifiers.remove(obj_src.modifiers[x])

    Delete_Object(obj_fin)
    bpy.context.scene.objects.active = obj_src
    #obj_src.select = False
    #obj_src.location[0] += -1
