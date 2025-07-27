#define MyAppName "ImageSorter"
#define MyAppVersion "2.0"
#define MyAppPublisher "Jessie"
#define MyAppExeName "ImageSorter.exe"

[Setup]
AppId={{12fbfb32-2a0f-476b-bf72-6ddb99010934}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={code:GetDefaultDirName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Installer
OutputBaseFilename=ImageSorter
SetupIconFile=assets\icons\app_icon.ico
Compression=lzma
SolidCompression=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
DisableProgramGroupPage=no
DisableDirPage=no
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "output\*"; DestDir: "{app}\output"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "utils\*"; DestDir: "{app}\utils"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: ""
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: ""; Tasks: desktopicon
Name: "{app}\{#MyAppName} (Portable)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--portable"; Check: not IsPortableModeCheck

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "{code:GetExeParameters}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{userappdata}\.image_sorter"

[Code]
var
  InstallModePage: TInputOptionWizardPage;
  IsPortableMode: Boolean;

function IsPortableModeCheck: Boolean;
begin
  Result := IsPortableMode;
  Log('IsPortableModeCheck: Returning ' + IntToStr(Ord(Result)));
end;

function GetDefaultDirName(Param: String): String;
begin
  if IsPortableMode then
  begin
    Result := ExpandConstant('{src}\ImageSorter');
    Log('GetDefaultDirName: Portable mode path = ' + Result);
  end
  else
  begin
    Result := ExpandConstant('{autopf}\{#MyAppName}');
    Log('GetDefaultDirName: Default mode path = ' + Result);
  end;
end;

function GetExeParameters(Param: String): String;
begin
  if IsPortableMode then
    Result := '--portable'
  else
    Result := '';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (PageID = wpSelectDir) and IsPortableMode then
  begin
    Result := True;
    Log('Skipping wpSelectDir because IsPortableMode = ' + IntToStr(Ord(IsPortableMode)));
  end;
  if (PageID = wpSelectProgramGroup) and IsPortableMode then
  begin
    Result := True;
    Log('Skipping wpSelectProgramGroup because IsPortableMode = ' + IntToStr(Ord(IsPortableMode)));
  end;
end;

procedure InitializeWizard;
begin
  InstallModePage := CreateInputOptionPage(wpWelcome,
    'Select Installation Type', 'Choose how you want to install {#MyAppName}',
    'Please select the installation type:', True, False);
  InstallModePage.Add('Default Installation (Installs to Program Files with uninstaller)');
  InstallModePage.Add('Portable Installation (Extracts to a single folder, no uninstaller)');
  InstallModePage.SelectedValueIndex := 0; // Default ke mode Default
  IsPortableMode := False; // Nilai default
  Log('InitializeWizard: IsPortableMode initialized to ' + IntToStr(Ord(IsPortableMode)));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True; // Default: lanjutkan
  if CurPageID = InstallModePage.ID then
  begin
    // Perbarui IsPortableMode saat tombol Next diklik di halaman pemilihan mode
    IsPortableMode := (InstallModePage.SelectedValueIndex = 1);
    if IsPortableMode then
      Log('Debug: IsPortableMode set to: True')
    else
      Log('Debug: IsPortableMode set to: False');
    // Atur path instalasi segera setelah IsPortableMode diperbarui
    if IsPortableMode then
    begin
      WizardForm.DirEdit.Text := ExpandConstant('{src}\ImageSorter');
      Log('NextButtonClick: Set path to ' + WizardForm.DirEdit.Text + ' for Portable mode');
    end
    else
    begin
      WizardForm.DirEdit.Text := ExpandConstant('{autopf}\{#MyAppName}');
      Log('NextButtonClick: Set path to ' + WizardForm.DirEdit.Text + ' for Default mode');
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then
  begin
    // Pastikan path instalasi sesuai pada halaman "Ready to Install"
    if IsPortableMode then
    begin
      WizardForm.DirEdit.Text := ExpandConstant('{src}\ImageSorter');
      Log('CurPageChanged (wpReady): Set path to ' + WizardForm.DirEdit.Text + ' for Portable mode');
    end
    else
    begin
      WizardForm.DirEdit.Text := ExpandConstant('{autopf}\{#MyAppName}');
      Log('CurPageChanged (wpReady): Set path to ' + WizardForm.DirEdit.Text + ' for Default mode');
    end;
  end;
end;

function WizardDirValue: String;
begin
  // Pastikan path yang digunakan oleh instalasi selalu sesuai
  if IsPortableMode then
  begin
    Result := ExpandConstant('{src}\ImageSorter');
    Log('WizardDirValue: Returning ' + Result + ' for Portable mode');
  end
  else
  begin
    Result := ExpandConstant('{autopf}\{#MyAppName}');
    Log('WizardDirValue: Returning ' + Result + ' for Default mode');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if IsPortableMode then
    begin
      CreateDir(ExpandConstant('{src}\ImageSorter'));
      Log('CurStepChanged (ssInstall): Created directory ' + ExpandConstant('{src}\ImageSorter') + ' for Portable mode');
    end;
  end
  else if CurStep = ssPostInstall then
  begin
    if IsPortableMode then
    begin
      DeleteFile(ExpandConstant('{group}\{#MyAppName}.lnk'));
      DeleteFile(ExpandConstant('{group}\{cm:UninstallProgram,{#MyAppName}}.lnk'));
      DeleteFile(ExpandConstant('{autodesktop}\{#MyAppName}.lnk'));
      RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' + '{#MyAppName}_is1');
      Log('CurStepChanged (ssPostInstall): Cleaned up registry and shortcuts for Portable mode');
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserConfigDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    if not IsPortableMode then
    begin
      UserConfigDir := ExpandConstant('{userappdata}\.image_sorter');
      if DirExists(UserConfigDir) then
      begin
        if MsgBox('Do you want to delete the configuration folder (.image_sorter)? This will remove all saved settings.', mbConfirmation, MB_YESNO) = IDYES then
        begin
          DelTree(UserConfigDir, True, True, True);
          Log('CurUninstallStepChanged: Deleted configuration folder ' + UserConfigDir);
        end;
      end;
    end;
  end;
end;