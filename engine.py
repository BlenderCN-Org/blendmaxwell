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

import os
import re
import time
import datetime
import math

import bpy
from bpy.types import RenderEngine

import numpy

from .log import log, LogStyles, LOG_FILE_PATH, copy_paste_log
from . import export
from . import ops
from . import system
from . import mxs
from . import maths


class MaxwellRenderExportEngine(RenderEngine):
    bl_idname = 'MAXWELL_RENDER'
    bl_label = 'Maxwell Render'
    bl_use_preview = True
    
    _t = None
    
    def render(self, scene):
        if(self.is_preview):
            self._material_preview(scene)
            return
        
        # # skip it completely..
        # s = scene.render
        # xr = int(s.resolution_x * s.resolution_percentage / 100.0)
        # yr = int(s.resolution_y * s.resolution_percentage / 100.0)
        # c = xr * yr
        # b = [[0.0, 0.0, 0.0, 1.0]] * c
        # r = self.begin_result(0, 0, xr, yr)
        # l = r.layers[0]
        # p = l.passes[0]
        # p.rect = b
        # self.end_result(r)
        pass
    
    def update(self, data, scene):
        if(self.is_preview):
            # self._material_preview(scene)
            return
        
        self._t = time.time()
        
        m = scene.maxwell_render
        
        bp = bpy.path.abspath(bpy.context.blend_data.filepath)
        # check if file is saved, if not raise error
        if(bp == ""):
            self.report({'ERROR'}, "Save file first.")
            return
        
        # other checks, like for camera (if not present, blender will raise error anyway)
        cams = [o for o in scene.objects if o.type == 'CAMERA']
        if(len(cams) == 0):
            self.report({'ERROR'}, "No Camera found in scene.")
            return
        
        ed = bpy.path.abspath(m.export_output_directory)
        # check if directory exists else error
        if(not os.path.exists(ed)):
            self.report({'ERROR'}, "Export directory does not exist.")
            return
        # check if directory if writeable else error
        if(not os.access(ed, os.W_OK)):
            self.report({'ERROR'}, "Export directory is not writeable.")
            return
        
        # set some workflow stuff..
        if(self.is_animation):
            m.exporting_animation_now = True
        else:
            m.exporting_animation_now = False
        if(scene.frame_start == scene.frame_current):
            m.exporting_animation_first_frame = True
        else:
            m.exporting_animation_first_frame = False
        m.private_image = m.output_image
        m.private_mxi = m.output_mxi
        m.exporting_animation_frame_number = scene.frame_current
        
        h, t = os.path.split(bp)
        n, e = os.path.splitext(t)
        if(m.exporting_animation_now and not m.exporting_animation_first_frame):
            mxs_name = m.private_name
            mxs_increment = m.private_increment
            mxs_suffix = m.private_suffix
        else:
            mxs_name = n
            mxs_increment = ""
            mxs_suffix = ""
        
        def walk_dir(p):
            """gets directory contents in format: {files:[...], dirs:[...]}"""
            r = {'files': [], 'dirs': [], }
            for (root, dirs, files) in os.walk(p):
                r['files'].extend(files)
                r['dirs'].extend(dirs)
                break
            return r
        
        if(m.exporting_animation_now):
            mxs_suffix = '_{:06d}'.format(m.exporting_animation_frame_number)
            if(m.export_incremental):
                # add or increment mxs number
                if(m.exporting_animation_first_frame):
                    # do this just once for a first frame
                    m.exporting_animation_first_frame = False
                    
                    dc = walk_dir(ed)
                    # get files from destination and filter all files starting with mxs_name and with .mxs extension
                    older = [f for f in dc['files'] if(f.startswith(mxs_name) and f.endswith(".mxs"))]
                    nn = 0
                    if(len(older) > 0):
                        older.sort()
                        pat = re.compile(str('^{0}.\d\d\d_\d\d\d\d\d\d.mxs$'.format(mxs_name)))
                        for ofn in older:
                            if(re.search(pat, ofn)):
                                # get increment number from each, if there is some of course
                                num = int(ofn[len(mxs_name) + 1:-len("_000000.mxs")])
                                if(nn < num):
                                    nn = num
                        nn += 1
                    if(nn != 0):
                        # there were some already incremented files, lets make nes increment from highest
                        mxs_increment = '.{:0>3}'.format(nn)
            elif(m.export_overwrite):
                # overwrite, no error reporting, no path changing
                pass
            else:
                # check and raise error if mxs exists, if not continue
                p = os.path.join(ed, "{}{}{}.mxs".format(mxs_name, mxs_increment, mxs_suffix))
                if(os.path.exists(p) and not m.export_overwrite):
                    # reset animation flags
                    self._reset_workflow(scene)
                    self.report({'ERROR'}, "Scene file already exist in Output directory.")
                    return
        else:
            if(m.export_incremental):
                # add or increment mxs number
                dc = walk_dir(ed)
                # get files from destination and filter all files starting with mxs_name and with .mxs extension
                older = [f for f in dc['files'] if(f.startswith(mxs_name) and f.endswith(".mxs"))]
                nn = 0
                if(len(older) > 0):
                    older.sort()
                    pat = re.compile(str('^{0}.\d\d\d.mxs$'.format(mxs_name)))
                    for ofn in older:
                        if(re.search(pat, ofn)):
                            # get increment number from each, if there is some of course
                            num = int(ofn[len(mxs_name) + 1:-len(".mxs")])
                            if(nn < num):
                                nn = num
                    nn += 1
                if(nn != 0):
                    # there were some already incremented files, lets make nes increment from highest
                    mxs_increment = '.{:0>3}'.format(nn)
            elif(m.export_overwrite):
                # overwrite, no error reporting, no path changing
                pass
            else:
                # check and raise error if mxs exists, if not continue
                p = os.path.join(ed, "{}{}{}.mxs".format(mxs_name, mxs_increment, mxs_suffix))
                if(os.path.exists(p) and not m.export_overwrite):
                    self._reset_workflow(scene)
                    self.report({'ERROR'}, "Scene file already exist in Output directory.")
                    return
        
        # store it to use it _render_scene (is this needed? it was in example.. i can do whole work here)
        # but the problem is, when exporting animation, this is called for each frame, so i got to store these props
        # maybe.. maybe not
        m.private_name = mxs_name
        m.private_increment = mxs_increment
        m.private_suffix = mxs_suffix
        m.private_path = os.path.join(ed, "{}{}{}.mxs".format(mxs_name, mxs_increment, mxs_suffix))
        m.private_basepath = os.path.join(ed, "{}{}.mxs".format(mxs_name, mxs_increment))
        
        try:
            s = scene.render.resolution_percentage / 100.0
            self.size_x = int(scene.render.resolution_x * s)
            self.size_y = int(scene.render.resolution_y * s)
            if(scene.name == 'preview'):
                pass
            else:
                self._render_scene(scene)
                m.output_image = m.private_image
                m.output_mxi = m.private_mxi
        except Exception as ex:
            import traceback
            m = traceback.format_exc()
            log(m)
            
            # import sys
            # import traceback
            # exc_type, exc_value, exc_traceback = sys.exc_info()
            # lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            # log("".join(lines))
            
            self._reset_workflow(scene)
            self.report({'ERROR'}, m)
        
        _d = datetime.timedelta(seconds=time.time() - self._t)
        log("export completed in {0}".format(_d), 1, LogStyles.MESSAGE)
    
    def _material_preview(self, scene):
        def get_material(scene):
            objects_materials = {}
            
            def get_instance_materials(ob):
                obmats = []
                if hasattr(ob, 'material_slots'):
                    for ms in ob.material_slots:
                        obmats.append(ms.material)
                if hasattr(ob.data, 'materials'):
                    for m in ob.data.materials:
                        obmats.append(m)
                return obmats
            
            for object in [ob for ob in scene.objects if ob.is_visible(scene) and not ob.hide_render]:
                for mat in get_instance_materials(object):
                    if mat is not None:
                        if object.name not in objects_materials.keys():
                            objects_materials[object] = []
                        objects_materials[object].append(mat)
            
            preview_objects = [o for o in objects_materials.keys() if o.name.startswith('preview')]
            if len(preview_objects) < 1:
                return
            
            mats = objects_materials[preview_objects[0]]
            if(len(mats) < 1):
                return None
            return mats
        
        mats = get_material(scene)
        
        def fill_black():
            xr = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
            yr = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
            c = xr * yr
            b = [[0.0, 0.0, 0.0, 1.0]] * c
            r = self.begin_result(0, 0, xr, yr)
            l = r.layers[0] if bpy.app.version < (2, 74, 4) else r.layers[0].passes[0]
            l.rect = b
            self.end_result(r)
        
        def fill_grid():
            xr = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
            yr = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
            c = xr * yr
            
            '''
            current_theme = bpy.context.user_preferences.themes.items()[0][0]
            theme_bg_col = bpy.context.user_preferences.themes[current_theme].image_editor.space.back
            
            def g(c):
                r = []
                for i, v in enumerate(c):
                    if(v <= 0.03928):
                        r.append(v / 12.92)
                    else:
                        r.append(math.pow((v + 0.055) / 1.055, 2.4))
                return r
            
            bg_col = g(theme_bg_col) + [1.0, ]
            
            a = 1.0 * maths.remap(8, 0, 100, 0.0, 1.0)
            grid_col = [bg_col[0] + a, bg_col[1] + a, bg_col[2] + a, 1.0]
            
            a = 1.0 * maths.remap(6, 0, 100, 0.0, 1.0)
            grid_col2 = [bg_col[0] + a, bg_col[1] + a, bg_col[2] + a, 1.0]
            '''
            
            bg_col = (48 / 256, 48 / 256, 48 / 256, 1.0)
            grid_col = (64 / 256, 64 / 256, 64 / 256, 1.0)
            
            pixels = numpy.array([bg_col] * c)
            pixels = numpy.reshape(pixels, (yr, xr, 4))
            for i in range(0, xr, 8):
                pixels[:, i] = grid_col
            for i in range(0, yr, 8):
                pixels[i] = grid_col
            
            def g(c):
                r = []
                for i, v in enumerate(c):
                    if(v <= 0.03928):
                        r.append(v / 12.92)
                    else:
                        r.append(math.pow((v + 0.055) / 1.055, 2.4))
                return r
            
            a1 = numpy.reshape(pixels, (-1, 4))
            a2 = []
            for c in a1:
                a2.append(g(c[:3]) + [1.0, ])
            
            r = self.begin_result(0, 0, xr, yr)
            l = r.layers[0] if bpy.app.version < (2, 74, 4) else r.layers[0].passes[0]
            l.rect = a2
            self.end_result(r)
        
        if(mats is not None):
            mat = mats[0]
            m = mat.maxwell_render
            
            # if(bpy.context.scene.maxwell_render_private.material != mat.name):
            #     bpy.context.scene.maxwell_render_private.material = mat.name
            # else:
            #     if(not m.flag):
            #         fill_black()
            #         return
            
            w = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
            h = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
            
            fill_black()
            
            # if(w, h) == (32, 32):
            #     # # skip icon rendering
            #     # fill_black()
            #     return
            
            # print(w, h)
            
            # bpy.data.materials[mat.name].maxwell_render.flag = False
            
            p = m.mxm_file
            if(p is not ''):
                p = os.path.realpath(bpy.path.abspath(p))
                a = None
                
                if(system.PLATFORM == 'Darwin'):
                    system.python34_run_mxm_preview(p)
                    d = os.path.join(os.path.split(os.path.realpath(__file__))[0], "support", )
                    f = os.path.split(p)[1]
                    npy = os.path.join(d, "{}.npy".format(f))
                    if(os.path.exists(npy)):
                        a = numpy.load(npy)
                    # cleanup
                    if(os.path.exists(npy)):
                        os.remove(npy)
                else:
                    a = mxs.read_mxm_preview(p)
                
                if(a is not None):
                    rw = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
                    rh = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
                    w, h, _ = a.shape
                    
                    # TODO: fix material preview drawing. at least when image is bigger then view, slice centered rectangle
                    
                    if((rw, rh) == (32, 32)):
                        # icon > slice to 32x32
                        # works pretty well, unless material has 25% preview..
                        d = int(w / 32)
                        a = a[:32 * d:d, :32 * d:d]
                    # elif(rw < w and rh < h):
                    #     # wd = int(w / rw)
                    #     # hd = int(h / rh)
                    #     # if(wd > hd):
                    #     #     d = wd
                    #     # else:
                    #     #     d = hd
                    #     # a = a[:rw * d:d, :rh * d:d]
                    #
                    #     if(rw < rh):
                    #         # wd = int(w / rw)
                    #         # hd = int(h / rh)
                    #         # a = a[:rw * wd:wd, :rh * hd:hd]
                    #         pass
                    #     else:
                    #         # d = int(h / rh)
                    #         d = int(w / rw)
                    #         a = a[:rh * d:d, :rh * d:d]
                    #
                    # elif(rw == w and rh == h):
                    #     pass
                    # elif(rw > w and rh > h):
                    #     pass
                    elif(w > rw):
                        # a = a[:rw:, :rw:]
                        a = a[:rw:, :rw:]
                    
                    w, h, _ = a.shape
                    # print(a.shape, rw, rh)
                    
                    # flip
                    a = numpy.flipud(a)
                    
                    # gamma correct
                    a.astype(float)
                    g = 2.2
                    a = (a[:] / 255) ** g
                    a = numpy.reshape(a, (w * h, 3))
                    z = numpy.empty((w * h, 1))
                    z.fill(1.0)
                    a = numpy.append(a, z, axis=1, )
                    
                    # draw
                    xr = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
                    yr = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
                    x = int((xr - w) / 2)
                    y = int((yr - h) / 2)
                    
                    r = self.begin_result(x, y, w, h)
                    l = r.layers[0] if bpy.app.version < (2, 74, 4) else r.layers[0].passes[0]
                    l.rect = a.tolist()
                    self.end_result(r)
                else:
                    # xr = int(scene.render.resolution_x * scene.render.resolution_percentage / 100.0)
                    # yr = int(scene.render.resolution_y * scene.render.resolution_percentage / 100.0)
                    # c = xr * yr
                    # b = [[0.0, 0.0, 0.0, 1.0]] * c
                    # r = self.begin_result(0, 0, xr, yr)
                    # l = r.layers[0] if bpy.app.version < (2, 74, 4) else r.layers[0].passes[0]
                    # l.rect = b
                    # self.end_result(r)
                    fill_grid()
            else:
                # fill_black()
                fill_grid()
    
    def _render_scene(self, scene):
        m = scene.maxwell_render
        p = m.private_path
        bp = m.private_basepath
        
        # write default one if not set, do not care if enabled, this is more usable when i change my mind later
        h, t = os.path.split(bp)
        n, e = os.path.splitext(t)
        if(m.output_image == ""):
            m.output_image = os.path.join(h, "{}.png".format(n))
            m.private_image = m.output_image
        if(m.output_mxi == ""):
            m.output_mxi = os.path.join(h, "{}.mxi".format(n))
            m.private_mxi = m.output_mxi
        
        def remove_increment(path):
            h, t = os.path.split(bpy.path.abspath(path))
            n, e = os.path.splitext(t)
            pat = re.compile(str('.\d\d\d{}$'.format(e)))
            if(re.search(pat, t)):
                n = t[:-len(".000{}".format(e))]
            return h, n, e
        
        if(m.export_incremental):
            # increment also both image files, and also do not care if enabled
            if(m.private_increment != ""):
                h, n, e = remove_increment(m.output_image)
                m.output_image = os.path.join(h, "{}{}{}".format(n, m.private_increment, e))
                h, n, e = remove_increment(m.output_mxi)
                m.output_mxi = os.path.join(h, "{}{}{}".format(n, m.private_increment, e))
        
        if(m.output_image_enabled):
            # if exporting animation add correct frame number
            if(m.exporting_animation_now):
                # frame number from image paths will be removed after export is finished in animation operator
                h, t = os.path.split(bpy.path.abspath(m.output_image))
                n, e = os.path.splitext(t)
                m.output_image = os.path.join(h, "{}{}{}".format(n, m.private_suffix, e))
        
        if(m.output_mxi_enabled):
            # if exporting animation add correct frame number
            if(m.exporting_animation_now):
                # frame number from image paths will be removed after export is finished in animation operator
                h, t = os.path.split(bpy.path.abspath(m.output_mxi))
                n, e = os.path.splitext(t)
                m.output_mxi = os.path.join(h, "{}{}{}".format(n, m.private_suffix, e))
        
        log_file_path = None
        ex = None
        
        # import cProfile, pstats, io
        # pr = cProfile.Profile()
        # pr.enable()
        
        ex = export.MXSExport(mxs_path=p, engine=self, )
        
        from .log import NUMBER_OF_WARNINGS
        if(NUMBER_OF_WARNINGS > 0):
            if(m.export_suppress_warning_popups):
                self.report({'WARNING'}, "There was {} warnings during export. Check log file for details.".format(NUMBER_OF_WARNINGS))
            else:
                self.report({'ERROR'}, "There was {} warnings during export. Check log file for details.".format(NUMBER_OF_WARNINGS))
            log("There was {} warnings during export. Check log file for details.".format(NUMBER_OF_WARNINGS), 1, LogStyles.WARNING, )
            
            if(m.export_warning_log_write):
                h, t = os.path.split(p)
                n, e = os.path.splitext(t)
                u = ex.uuid
                log_file_path = os.path.join(h, '{}-export_log-{}.txt'.format(n, u))
                copy_paste_log(log_file_path)
        
        # pr.disable()
        # s = io.StringIO()
        # sortby = 'cumulative'
        # ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        # ps.print_stats()
        # print(s.getvalue())
        
        if((m.exporting_animation_now and scene.frame_current == scene.frame_end) or not m.exporting_animation_now):
            if(m.export_log_open):
                if(log_file_path is not None):
                    # open local, it gets written only when some warnigns are encountered
                    system.open_file_in_default_application(log_file_path)
                else:
                    # else open global log file from inside addon files
                    system.open_file_in_default_application(LOG_FILE_PATH)
        
        # open in..
        if(ex is not None and not m.exporting_animation_now):
            bpy.ops.maxwell_render.open_mxs(filepath=ex.mxs_path, application=m.export_open_with, instance_app=m.instance_app, )
    
    def _reset_workflow(self, scene):
        m = scene.maxwell_render
        m.exporting_animation_now = False
        m.exporting_animation_frame_number = 1
        m.exporting_animation_first_frame = True
        m.private_name = ""
        m.private_increment = ""
        m.private_suffix = ""
        m.private_path = ""
        m.private_basepath = ""
        m.private_image = ""
        m.private_mxi = ""
