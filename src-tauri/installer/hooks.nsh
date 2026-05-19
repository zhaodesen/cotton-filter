; 安装前先结束正在运行的应用与 Python sidecar。
; 否则旧的 cotton-filter-backend.exe 仍在运行并锁定文件，
; NSIS 覆盖写入时会报 "Error opening file for writing"。
!macro NSIS_HOOK_PREINSTALL
  nsExec::Exec 'taskkill /F /T /IM "cotton-filter-backend.exe"'
  Pop $0
  nsExec::Exec 'taskkill /F /T /IM "cotton-filter.exe"'
  Pop $0
  ; 给操作系统一点时间释放文件句柄。
  Sleep 800
!macroend

; 卸载前同样结束进程，保证目录能被完整删除。
!macro NSIS_HOOK_PREUNINSTALL
  nsExec::Exec 'taskkill /F /T /IM "cotton-filter-backend.exe"'
  Pop $0
  nsExec::Exec 'taskkill /F /T /IM "cotton-filter.exe"'
  Pop $0
  Sleep 500
!macroend
