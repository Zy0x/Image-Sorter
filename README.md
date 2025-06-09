## 🖼️ Image Sorter

> A sleek and powerful image sorting application with drag & drop support, undo functionality, and customizable themes.

[![License](https://img.shields.io/github/license/Zy0x/ImageSorter)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0-blue)]()
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()

<p align="center">
  <img src="assets/demo.gif" width="700" alt="Demo GIF">
</p>

---

### 🧾 Description

**Image Sorter** is a modern, cross-platform desktop app built using **PySide6**, designed to help users effortlessly organize thousands of images into custom folders with just one click. Featuring a clean UI, dark/light mode toggle, keyboard shortcuts, and intuitive folder navigation — this tool streamlines the workflow for photographers, designers, and anyone managing large image collections.

---

### ✨ Features

✔️ Effortless image sorting into custom folders  
✔️ Undo functionality (`Ctrl+Z`)  
✔️ Drag & Drop support (folders/images)  
✔️ Responsive image previews with smooth transitions  
✔️ Customizable themes (including system theme detection)  
✔️ Recent folders history  
✔️ Keyboard shortcuts (`1–5`, `←/→`, `Space`, `Ctrl+Z`)  
✔️ Filter by extension (`.png`, `.jpg`, etc.)  
✔️ Export/import settings  
✔️ Log export for tracking activity  
✔️ Folder editor for destination paths  
✔️ Progress bar on loading  
✔️ On-screen notifications  
✔️ Multi-resolution image handling  

---

### 🔧 Requirements

Before running, make sure you have installed:

```bash
python >= 3.8
```

Install dependencies using:

```bash
pip install -r requirements.txt
```

#### 📄 `requirements.txt`

```txt
PySide6>=6.0.0
pillow>=9.0.0
```

---

### 🚀 How to Run

1. **Download the Project:**
   - Download the ZIP file from the repository.
   - Extract the ZIP file to a folder of your choice.

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Build the Application:**
   - Open a terminal or command prompt in the project directory.
   - Run the following command:
     ```bash
     build.bat
     ```
   - This will generate an executable file in the `ImageSorter` folder.

4. **Run the Executable:**
   - Navigate to the `ImageSorter` folder.
   - Double-click the generated executable file to launch the application.

---

### 🛠️ Folder Structure

```
ImageSorter/
├── assets/
│   ├── icons/
│   └── screenshots/
├── config/
│   ├── settings.json     # App configuration
│   └── event.log         # Activity log
├── utils/
│   └── image_utils.py    # Image resizing logic
├── main.py               # Main application logic
├── README.md
└── requirements.txt
```

---

### 🎨 Themes

You can switch between:
- Light Mode
- Dark Mode
- System Default
- Custom Theme (via Settings > Customize Theme)

Customize colors for:
- Background
- Text
- Buttons
- Labels
- Borders
- Shadows

---

### 📦 Export / Import

- **Export Settings**: Save your folder names, paths, and theme preferences.
- **Import Settings**: Load saved settings from a JSON file.
- **Export Log**: Track all actions taken during usage.

---

### 🌐 License

MIT License – see [LICENSE](LICENSE) for details.

---

### 👤 Author

👤 **Zy0x**

- GitHub: [@Zy0x](https://github.com/Zy0x)
- Telegram: [@Thea](https://t.me/ThuandMuda)

---

### 🙌 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

---

### 📷 Screenshots

| Light Mode | Dark Mode |
|------------|-----------|
| ![Light Mode](assets/screenshots/light.png) | ![Dark Mode](assets/screenshots/dark.png) |

---

### 📬 Feedback

If you have any suggestions, bug reports, or want to contribute, please open an issue or reach out via Telegram or GitHub.

---

> Built with ❤️ using Python & PySide6  
> "Organize your photos in seconds — effortlessly."

---

### 📂 Build Instructions

To build the application from source, follow these steps:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Zy0x/ImageSorter.git
   cd ImageSorter
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Build Script:**
   ```bash
   build.bat
   ```

4. **Run the Application:**
   - The executable will be located in the `ImageSorter` folder after building.
   - Double-click the executable to launch the app.

---

### 🏗️ Development Notes

- **Resources Compilation:** Before building, ensure that `res_compiler.bat` has been run to compile resources (e.g., icons, images).
- **Customization:** You can customize the application's appearance and behavior through the `settings.json` file in the `config` directory.
- **Cross-Platform Compatibility:** The application supports Windows, macOS, and Linux when built correctly.

---

### 📝 Credits

- Icons by [Icons8](https://icons8.com/)
- Powered by [PySide6](https://wiki.qt.io/PySide6)
- Inspired by minimalistic media organizers
