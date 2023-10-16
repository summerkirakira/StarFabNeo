import os

os.environ['PYSIDE_DESIGNER_PLUGINS'] = "."
os.environ["QT_LOGGING_RULES"] = '*.debug=false;qt.pysideplugin=false'


from starfab.main import main

main()
