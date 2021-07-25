"""
SCDV BlenderLink

This is the BlenderLink client that is meant to be accessed from with a Blender instance that has been launched from
SCDV. If so, it will use the already have the correct port and a valid auth token.

You can user :func:`blenderlink_connect` to connect from a Blender that has the correct python path's/modules available
to manually connect to SCDV.

"""
import os
import typing

try:
    import bpy
    from functools import partial

    from bpy.props import IntProperty, StringProperty

    from rpyc.core.stream import SocketStream
    from rpyc.core.service import ClassicService
    from rpyc.utils.factory import connect_stream

    import scdv

    from .conf import LINK_TOKEN_LEN
    from .utils import parse_auth_token, get_blenderlink_config_port


    class _BlenderLinkClient:
        def __init__(self):
            self._conn = None
            self.link_id = None
            self.link_token = None
            self.port = None
            self._orig_get_scdv = None

        def setup_monkeypatch(self):
            if self._orig_get_scdv is None:
                self._orig_get_scdv = scdv.get_scdv
                scdv.get_scdv = self._conn.modules.scdv.get_scdv

        @property
        def scdv(self):
            if self._conn is not None:
                return self._conn.modules.scdv.get_scdv()

        def connect(self, port=None, token=None, monitor: typing.Callable = print):
            port = port or os.environ.get('SCDV_BLENDERLINK_PORT')
            blend_token = token or os.environ.get('SCDV_BLENDERLINK_TOKEN')

            if self.is_connected():
                self.disconnect()

            if port is None:
                port = get_blenderlink_config_port()

            if blend_token is None or blend_token == '*':
                token = '*'
                blend_token = f'{os.getpid()}:'
                blend_token += '*' * (LINK_TOKEN_LEN - len(blend_token))
                print(f'Requesting authentication from SCDV - check SCDV to approve.')

            if port:
                monitor(f"Connecting to SCDV BlenderLink localhost:{port} [{blend_token}].")
                try:
                    s = SocketStream.connect('localhost', port)
                except ConnectionRefusedError:
                    monitor(f"Could not connect, is blenderlink started?")
                    return None

                s.write(blend_token.encode('utf-8'))
                try:
                    resp_token = s.read(LINK_TOKEN_LEN).decode('utf-8')
                    bid, blend_token = parse_auth_token(resp_token)
                    self._conn = connect_stream(stream=s, service=ClassicService)
                    if bid is not None:
                        self.link_id = bid
                        self.link_token = blend_token
                    self._conn.ping()
                    self.port = port
                except Exception:
                    if token is None:
                        # could've had an old token, try to connect to the current SCDV, rereading the port
                        return self.connect(port=None, token='*')
                    else:
                        monitor('SCDV BlenderLink connection failed.')
                        self._conn = None
            return self._conn

        def disconnect(self):
            if self._conn:
                self._conn.close()
                self._conn = None
            if self._orig_get_scdv is not None:
                scdv.get_scdv = self._orig_get_scdv
                self._orig_get_scdv = None

        def is_connected(self):
            try:
                if self._conn is not None:
                    self._conn.ping()
                    return True
            except EOFError:
                if self._conn is not None:
                    self.disconnect()
            return False


    blenderlink_client = _BlenderLinkClient()


    class BlenderLinkConnectOperator(bpy.types.Operator):
        """ Connect to SCDV BlenderLink. Will do nothing if there is already an active BlenderLink connection """
        bl_idname = 'scdv.blenderlink_connect'
        bl_label = 'SCDV Blender Link Connect'

        port: IntProperty(default=-1)
        token: StringProperty(default='')

        def execute(self, context):
            port = self.port if self.port > 0 else None
            token = self.token if self.token else None
            if not blenderlink_client.is_connected():
                blenderlink_client.connect(port, token, monitor=partial(self.report, {'INFO'}))
            if blenderlink_client.is_connected():
                blenderlink_client.setup_monkeypatch()
                context.scene.scdv_bl_port = int(blenderlink_client.port)
                return {'FINISHED'}
            self.report({'ERROR'}, f"Failed to connect SCDV Blender Link")
            return {'CANCELLED'}


    class BlenderLinkDisconnectOperator(bpy.types.Operator):
        """ Disconnect SCDV BlenderLink """
        bl_idname = 'scdv.blenderlink_disconnect'
        bl_label = 'SCDV Blender Link Disconnect'

        def execute(self, context):
            if blenderlink_client.is_connected():
                blenderlink_client.disconnect()
            return {'FINISHED'} if not blenderlink_client.is_connected() else {'CANCELLED'}


    class BlenderLinkPanel(bpy.types.Panel):
        bl_label = 'SCDV Blender Link'
        bl_idname = 'VIEW3D_PT_BlenderLink_Panel'
        bl_category = 'SCDV'
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_context = ""

        def draw(self, context):
            layout = self.layout

            if blenderlink_client.is_connected():
                layout.row().label(text=f'Connected', icon='RADIOBUT_ON')
            else:
                layout.row().label(text=f'Disconnected', icon='RADIOBUT_OFF')

            row = layout.row()
            row.prop(context.scene, "scdv_bl_port", text="Port")
            row.enabled = not blenderlink_client.is_connected()

            row = layout.row()
            if blenderlink_client.is_connected():
                row.operator("scdv.blenderlink_disconnect", text='Disconnect')
            else:
                row.operator("scdv.blenderlink_connect", text='Connect')


    def register():
        try:
            bpy.utils.register_class(BlenderLinkConnectOperator)
            bpy.utils.register_class(BlenderLinkDisconnectOperator)
            bpy.utils.register_class(BlenderLinkPanel)
            default_port = int(os.environ.get('SCDV_BLENDERLINK_PORT', get_blenderlink_config_port() or 0))
            bpy.types.Scene.scdv_bl_port = IntProperty(name='SCDV BlenderLink Port', default=default_port)
        except (ValueError, RuntimeError):
            pass  # already registered


    def unregister():
        blenderlink_client.disconnect()
        bpy.utils.unregister_class(BlenderLinkConnectOperator)
        bpy.utils.unregister_class(BlenderLinkDisconnectOperator)
        bpy.utils.unregister_class(BlenderLinkPanel)
        del bpy.types.Scene.scdv_bl_port


    def client_init():
        """ Called when SCDV launches Blender """
        register()
        bpy.ops.scdv.blenderlink_connect()

except ImportError:
    pass  # If we're not in blender just be silent