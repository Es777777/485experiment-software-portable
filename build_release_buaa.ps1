$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distRoot = Join-Path $projectRoot "dist"
$releaseVersion = "v1.0.1"
$releaseDate = Get-Date -Format "yyyyMMdd"
$zipName = "485experiment-software-portable-buaa-$releaseVersion-$releaseDate.zip"

Set-Location $projectRoot

& powershell -ExecutionPolicy Bypass -File (Join-Path $projectRoot "build_release.ps1")

$env:BUAA_ZIP_NAME = $zipName

py -3 -c "from pathlib import Path; import os, shutil, zipfile; project_root = Path.cwd(); dist_root = project_root / 'dist'; app_dist = dist_root / '\u5b9e\u9a8c\u8f6f\u4ef6'; buaa_dist = dist_root / '\u5b9e\u9a8c\u8f6f\u4ef6_\u5317\u822a\u7279\u4f9b\u7248'; shutil.rmtree(buaa_dist, ignore_errors=True); shutil.copytree(app_dist, buaa_dist); shutil.copyfile(project_root / 'config' / 'edition_profile.buaa.json', buaa_dist / 'config' / 'edition_profile.json'); readme = buaa_dist / 'README.txt'; note = '\n\n\u5317\u822a\u7279\u4f9b\u7248\u8bf4\u660e\n- \u672c\u7248\u672c\u4f1a\u5c06 T1/T2/T3 \u4ee5\u53ca\u7531\u5176\u63a8\u5bfc\u7684 M_y\u3001M_x\u3001M\u3001theta \u7edf\u4e00\u6309 1/3 \u7cfb\u6570\u6362\u7b97\u3002\n- \u603b\u7535\u6d41\u3001\u5e73\u5747\u5408\u529b\u548c\u539f\u59cb\u91c7\u6837\u5217\u4fdd\u6301\u539f\u59cb\u53e3\u5f84\u4e0d\u53d8\u3002\n'; readme.write_text(readme.read_text(encoding='utf-8') + note, encoding='utf-8'); zip_path = dist_root / os.environ['BUAA_ZIP_NAME'];
if zip_path.exists(): zip_path.unlink();
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for item in buaa_dist.rglob('*'):
        if item.is_file():
            zf.write(item, item.relative_to(buaa_dist));
print(f'BUAA portable release zip created at: {zip_path}')"
