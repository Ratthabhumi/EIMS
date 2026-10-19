# Shared source analyses; two normal Windows manifests and one COLLECT directory.
from pathlib import Path

source = Path(SPECPATH)
options = dict(pathex=[str(source)], binaries=[], datas=[], hiddenimports=[],
               hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['pytest'],
               noarchive=False, optimize=0)
standard = Analysis([str(source / 'portable_standard.py')], **options)
admin = Analysis([str(source / 'portable_admin.py')], **options)
standard_exe = EXE(PYZ(standard.pure), standard.scripts, [], exclude_binaries=True,
                   name='EIMS-Auditor-Standard', console=False, uac_admin=False,
                   debug=False, strip=False, upx=False)
admin_exe = EXE(PYZ(admin.pure), admin.scripts, [], exclude_binaries=True,
                name='EIMS-Auditor-Admin', console=False, uac_admin=True,
                debug=False, strip=False, upx=False)
package = COLLECT(standard_exe, admin_exe, standard.binaries, admin.binaries,
                  standard.datas, admin.datas, strip=False, upx=False,
                  name='EIMS_USB_Auditor')
