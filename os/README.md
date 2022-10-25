The Maya devkit contains all necessary files for building cmdc, except the Python library itself. These are those missing libraries. As it turns out, the library is (luckily) binary identical across all versions of Maya.

Can be confirmed with:

```pwsh
function CompareFiles {
    param(
    [string]$Filepath1,
    [string]$Filepath2
    )
    if ((Get-FileHash $Filepath1).Hash -eq (Get-FileHash $Filepath2).Hash) {
        Write-Host 'Files Match' -ForegroundColor Green
    } else {
        Write-Host 'Files do not match' -ForegroundColor Red
    }
}

$maya2020 = 'C:\Program Files\Autodesk\Maya2020\lib\python27.lib'
$maya2019 = 'C:\Program Files\Autodesk\Maya2019\lib\python27.lib'
CompareFiles $maya2020 $maya2019
# Files Match
```
