; TexPaste Setup Script for Inno Setup 6
; Version: 1.0.0
; Author: StoneLL1
; GitHub: https://github.com/StoneLL1/TexPaste

#define MyAppName "TexPaste"
#define MyAppPublisher "StoneLL1"
#define MyAppURL "https://github.com/StoneLL1/TexPaste"
#define MyAppExeName "TexPaste.exe"

; Read version from config.default.json (preprocessor)
; Note: Version should be updated manually or via build script
#define MyAppVersion "1.0.0"

[Setup]
AppId={{8A7C9D6B-1234-5678-9ABC-DEF012345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=license.txt
OutputDir=..\dist
OutputBaseFilename=TexPaste-Setup-{#MyAppVersion}
SetupIconFile=..\src\resources\icons\texpaste.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=TexPaste - LaTeX OCR and Smart Paste Tool
VersionInfoCopyright=Copyright (C) 2024 StoneLL1
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; Disable welcome page (modern style doesn't need it)
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.InstallPandoc=Install Pandoc converter
english.InstallPandocDesc=Pandoc converts LaTeX/Markdown to Word format for smart paste feature
english.PandocDetected=Pandoc is already installed on your system
english.PandocNotFound=Pandoc not found. Recommended for Word/WPS smart paste feature
english.InstallingPandoc=Installing Pandoc...
english.PandocInstallFailed=Pandoc installation failed. You may need to install it manually
english.CreateDesktopIcon=Create desktop shortcut
english.AutoStart=Launch at startup
english.LaunchProgram=Launch TexPaste

[Files]
; Main executable
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Shortcut icon (white background for better visibility on Windows)
Source: "..\src\resources\icons\texpaste_quick.ico"; DestDir: "{app}"; Flags: ignoreversion

; Pandoc MSI (conditional - only if not detected)
Source: "pandoc\pandoc-*-windows-x86_64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsPandocInstalled

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\texpaste_quick.ico"
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\texpaste_quick.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Windows\Start Menu\Programs\Startup\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\texpaste_quick.ico"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#MyAppName}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}"; ValueType: string; ValueName: "UninstallString"; ValueData: "{uninstallexe}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\{#MyAppExeName}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}"; ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#MyAppURL}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#MyAppVersion}"

[Code]
var
  PandocDetected: Boolean;

// Check if Pandoc is installed in system PATH
function IsPandocInstalled: Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  // Try to run pandoc --version
  if Exec('pandoc.exe', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := (ResultCode = 0);
  end;
end;

// Initialize wizard - detect Pandoc before showing pages
procedure InitializeWizard;
begin
  PandocDetected := IsPandocInstalled();
end;

// Skip ready page if Pandoc is already installed (no need to show options)
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

// CurStepChanged - called during installation
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  PandocMSI: String;
  FindRec: TFindRec;
begin
  if CurStep = ssPostInstall then
  begin
    // Install Pandoc if not detected and MSI file exists
    if not PandocDetected then
    begin
      // Find the Pandoc MSI file in {tmp}
      if FindFirst(ExpandConstant('{tmp}\pandoc-*-windows-x86_64.msi'), FindRec) then
      begin
        PandocMSI := ExpandConstant('{tmp}\') + FindRec.Name;
        FindClose(FindRec);

        // Silent install Pandoc using msiexec
        if Exec('msiexec.exe',
                '/i "' + PandocMSI + '" /quiet /norestart ADDLOCAL=ALL',
                '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        begin
          if ResultCode <> 0 then
          begin
            Log('Pandoc installation returned code: ' + IntToStr(ResultCode));
          end;
        end
        else
        begin
          Log('Failed to execute Pandoc installer');
        end;
      end;
    end;
  end;
end;

// Update ready memo to show Pandoc status
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  PandocStatus: String;
begin
  Result := '';

  if MemoDirInfo <> '' then
    Result := Result + MemoDirInfo + NewLine + NewLine;

  if MemoGroupInfo <> '' then
    Result := Result + MemoGroupInfo + NewLine + NewLine;

  if MemoTasksInfo <> '' then
    Result := Result + MemoTasksInfo + NewLine + NewLine;

  // Show Pandoc status
  if PandocDetected then
    PandocStatus := ExpandConstant('{cm:PandocDetected}')
  else
    PandocStatus := ExpandConstant('{cm:InstallPandoc}');

  Result := Result + Space + 'Pandoc:' + NewLine + Space + Space + PandocStatus;
end;

// Called before installation starts
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  NeedsRestart := False;
end;