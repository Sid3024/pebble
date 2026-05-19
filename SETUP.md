# Development Setup

## 1. Prerequisites
- **Git:** Must be installed. Download from [git-scm.com/install/windows](https://git-scm.com/install/windows).
- **Visual Studio Code:** Download and install from [code.visualstudio.com](https://code.visualstudio.com/).
- **PlatformIO IDE Extension:** Install the PlatformIO IDE extension from the VS Code Marketplace.

## 2. Creating Your Repository (Template)
Do **not** clone this project directly. Instead, use it as a template to create your own repository.

1. Go to the original repository: [https://github.com/SustainableLivingLab/UTC_2738_STEER](https://github.com/SustainableLivingLab/UTC_2738_STEER)
2. Click the green **"Use this template"** button near the top right.

![GitHub Use This Template Button](assets/github-use-this-template-button.png)

3. Select **"Create a new repository"**.
4. **Name your repo:** Use your specific project name. Use **underscores** (e.g., `My_Project_Name`) instead of spaces to prevent issues.
5. Once your new repository is created, click the **"Code"** button and copy your repository's URL.

## 3. Cloning Your Project
Now that you have your own repository, clone it to your local machine using VS Code.

1. Open VS Code.
2. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS) to open the Command Palette.
3. Type `Git: Clone` and press Enter.
4. Paste **your repository URL** (the one you created in the previous step).
5. Select a local folder to save the project and click **Open** when prompted.

## 4. Opening the Project
1. Open Visual Studio Code.
2. Click on the **PlatformIO** icon on the left sidebar (looks like an ant).
3. Select **Pick a folder** (or **Open Project**) and navigate to the `UTC_2738_STEER` directory.

## 5. Building and Uploading
- Many students miss the build button in the VS Code status bar. If you cannot find it, open the **PlatformIO** sidebar and use **PROJECT TASKS** -> **seeed-xiao-esp32-s3-plus** -> **General** -> **Build**.

![PlatformIO Build Button](assets/platformio-build-button.png)

- **Build:** Click **Build** in the PlatformIO task list shown above, or click the **Checkmark** icon in the VS Code status bar.
- **Upload:** Click **Upload** in the same PlatformIO task list, or click the **Right Arrow** icon in the VS Code status bar.
- **Serial Monitor:** Click **Monitor** in the same PlatformIO task list, or click the **Plug** icon in the VS Code status bar.

## 6. Command Line Usage
If you prefer using the terminal, always use the absolute path to the PlatformIO executable as configured for this environment:
- **Build:**
  ```powershell
  C:\Users\teren\.platformio\penv\Scripts\pio.exe run --environment seeed-xiao-esp32-s3-plus
  ```
- **Upload:**
  ```powershell
  C:\Users\teren\.platformio\penv\Scripts\pio.exe run --target upload --environment seeed-xiao-esp32-s3-plus
  ```
- **Monitor:**
  ```powershell
  C:\Users\teren\.platformio\penv\Scripts\pio.exe device monitor
  ```

## 7. Refreshing IntelliSense Metadata
If VS Code reports that it cannot resolve the ESP32-S3 compiler path and falls back to `cl.exe`, regenerate the PlatformIO compilation database:

```powershell
C:\Users\teren\.platformio\penv\Scripts\platformio.exe run -t compiledb -e seeed-xiao-esp32-s3-plus
```

This refreshes the generated C/C++ configuration and `compile_commands.json` used by IntelliSense.

## 8. Starting Your Own Project
Once you have successfully built and tested the template code, you can begin your own project.

1. **Clean up:** You can remove the existing source code in the `src/` directory.
2. **Your Code:** Start writing your own firmware in the `src/` directory (e.g., `main.cpp`).

## 9. Documentation (README.md)
It is important to document your project properly. Please **replace the content** of your `README.md` with the following structure:

1. **Title:** Clear name for your project.
2. **Team Name and Members:** List your team name and all members involved.
3. **App Description:** 
    - **Project Goals:** What does your application do?
    - **Hardware:** List all hardware components used.
    - **Software Setup:** Briefly mention any specific libraries or configurations.
    - **Usage:** How should someone interact with your finished project?

## 10. AI Setup (AI.md)
You are encouraged to use AI tools (like ChatGPT, Copilot, etc.) responsibly. Please refer to the `AI.md` file for instructions on:
- How to set up and configure AI tools for this project.
- Best practices for using AI in development.
- How to document your AI usage and verification.
