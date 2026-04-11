from pathlib import Path
import runpy


if __name__ == '__main__':
    root_script = Path(__file__).resolve().parents[1] / 'debug_config_273.py'
    runpy.run_path(str(root_script), run_name='__main__')
