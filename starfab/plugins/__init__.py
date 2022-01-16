import pkgutil
import logging
import importlib

from scdatatools import plugins as _scdt_plugins

logger = logging.getLogger(__name__)


class StarFabPlugin(_scdt_plugins.DataToolsPlugin):
    default_settings = {}

    def register(self):
        pass

    def unregister(self):
        pass


class StarFabPluginManager(_scdt_plugins.PluginManager):
    PACKAGE_PREFIX = "starfab_"
    PLUGIN_CLASS = StarFabPlugin


########################################################################################################
# region singleton access methods
plugin_manager = StarFabPluginManager()
register_plugin = plugin_manager.register_plugin
unregister_plugin = plugin_manager.unregister_plugin
register_hook = plugin_manager.register_hook
unregister_hook = plugin_manager.unregister_hook
# endregion singleton access methods
########################################################################################################


def register(plugin: StarFabPlugin):
    """ Decorator to register a `DataToolsPlugin`

    @plugins.register
    class MyPlugin(DataToolsPlugin):
        ...

    """
    register_plugin(plugin)
    return plugin
