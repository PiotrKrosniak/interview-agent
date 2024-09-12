import flet as ft
import pypdf
import os

SAVE_FILE_PATH = "uploaded_cv_text.txt"  # Path to save the CV text content
POSITION_FILE_PATH = "position_name.txt"  # Path to save the position name

def cvupload_page(page):
    # Load previously saved content if it exists
    def load_saved_content():
        if os.path.exists(SAVE_FILE_PATH):
            with open(SAVE_FILE_PATH, "r") as file:
                return file.read()
        return ""

    # Load previously saved position name if it exists
    def load_saved_position_name():
        if os.path.exists(POSITION_FILE_PATH):
            with open(POSITION_FILE_PATH, "r") as file:
                return file.read()
        return ""

    # Save the position name when changed
    def save_position_name(e):
        with open(POSITION_FILE_PATH, "w") as file:
            file.write(position_name.value)

    # File picker result handler
    def on_file_picker_result(e: ft.FilePickerResultEvent):
        if e.files:
            selected_files.value = ", ".join([f.name for f in e.files])
            # Store the path of the uploaded file
            uploaded_file_path.value = e.files[0].path
            # Read and display the content of the PDF file
            with open(uploaded_file_path.value, 'rb') as f:
                reader = pypdf.PdfReader(f)
                text_content = ""
                for page_num in range(len(reader.pages)):
                    text_content += reader.pages[page_num].extract_text()
            
            # Set the result_text content
            result_text.value = text_content

            # Save the extracted text to a file
            with open(SAVE_FILE_PATH, "w") as file:
                file.write(text_content)

        else:
            selected_files.value = "File selection canceled."
        
        selected_files.update()
        result_text.update()

    # Initialize file picker and add to overlay
    file_picker = ft.FilePicker(on_result=on_file_picker_result)
    page.overlay.append(file_picker)

    # Display the selected file
    selected_files = ft.Text()
    uploaded_file_path = ft.Text(value="", visible=False)

    # TextField for showing the content of the PDF file
    result_text = ft.TextField(
        value=load_saved_content(),  # Load saved content when the app starts
        read_only=True,
        multiline=True,
        expand=True
    )

    # Text field for position name
    position_name = ft.TextField(
        label="Position Name",
        value=load_saved_position_name(),  # Load saved position name when the app starts
        on_change=save_position_name  # Save the position name when changed
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Text("Upload Your CV", size=24, weight="bold"),
                ft.Text("Please enter the position you are applying for:"),  # Description above text input field
                position_name,  # Add position name text field
                ft.Text("Please upload your CV file:"),  # Description above file upload
                ft.ElevatedButton(
                    "Select CV File",
                    on_click=lambda _: file_picker.pick_files(
                        allow_multiple=False, 
                        allowed_extensions=["pdf"]
                    )
                ),
                selected_files,
                ft.Container(
                    content=result_text,  # Display the content of the PDF file
                    expand=True
                )
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=10,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
