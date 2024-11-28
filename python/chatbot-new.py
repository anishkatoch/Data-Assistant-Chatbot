import os
import re
import csv
import sqlite3
import pandas as pd
import speech_recognition as sr
from langchain import OpenAI, SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
import streamlit as st
from streamlit_chat import message
import sys
import pyttsx3
import base64
import threading
import html

st.set_page_config(layout="wide")


def run_tts(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()

def display_message_with_avatar_and_voice(message_text, is_user=True, index=None):
    escaped_message_text = html.escape(message_text)

    if is_user:
        # User message without any icons
        message_html = f'<div class="user-message">{escaped_message_text}</div>'
    else:
        # Bot message without any icons
        message_html = f'<div class="bot-message">{escaped_message_text}</div>'

    st.markdown(message_html, unsafe_allow_html=True)

# def display_message_with_avatar_and_voice(message_text, is_user=True, index=None):
#     escaped_message_text = html.escape(message_text)
#
#     if is_user:
#         message_html = f'<div class="user-message">{escaped_message_text} <img src="data:image/png;base64,{copy_icon}" class="copy-icon" id="copy-icon-{index}" onclick="copyToClipboard(`{escaped_message_text}`)"></div>'
#     else:
#         message_html = f'<div class="bot-message">{escaped_message_text} <img src="data:image/png;base64,{voice_icon}" class="voice-icon" id="voice-icon-{index}"><img src="data:image/png;base64,{copy_icon}" class="copy-icon" id="copy-icon-{index}" onclick="copyToClipboard(`{escaped_message_text}`)"></div>'
#
#     st.markdown(message_html, unsafe_allow_html=True)


# voice_icon_path = r"C:\Users\Pro\Downloads\images.png" # Update this path
# voice_icon = base64.b64encode(open(voice_icon_path, "rb").read()).decode()


# copy_icon_path = r"C:\Users\Pro\Downloads\images (2).jpg"  # Update this path
# copy_icon = base64.b64encode(open(copy_icon_path, "rb").read()).decode()

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background-color: #D3D3D3;
    }
    .user-message {
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 10px;
        border-radius: 10px;
        max-width: 60%;
        margin-left: auto;
        margin-right: 0;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    .bot-message {
        background-color: #fff3cd;
        color: #664d03;
        padding: 10px;
        border-radius: 10px;
        max-width: 60%;
        margin-left: 0;
        margin-right: auto;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    .voice-icon {
        cursor: pointer;
        margin-left: 10px;
    }
    .copy-icon {
        cursor: pointer;
        margin-left: 10px;
    }
    .feedback-buttons {
        display: flex;
        justify-content: center;
        margin-top: 10px;
    }
    .feedback-buttons button {
        margin: 0 5px;
        padding: 5px 10px;
        font-size: 12px;
    }
    </style>
    <script>
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(function() {
            console.log('Copying to clipboard was successful!');
        }, function(err) {
            console.error('Could not copy text: ', err);
        });
    }
    </script>
    """,
    unsafe_allow_html=True
)


def fetch_answer(question):
    global dbChain
    """Fetch the answer for a given question from the database."""
    return dbChain.run(question)


def main():
    global dbChain, dataset_name
    recognizer = sr.Recognizer()

    st.markdown("""
        <style>
            .main {
                border: 2px solid #ccc;
                padding: 20px;
                border-radius: 10px;
                margin: 10px;
                background-color: #FFFFFF;
            }
        </style>
        """, unsafe_allow_html=True)

    def recognize_speech_from_mic():
        with sr.Microphone() as source:
            st.info("Adjusting for ambient noise, please wait...")
            recognizer.adjust_for_ambient_noise(source, duration=5)
            st.info("Listening for your speech...")
            audio_data = recognizer.listen(source)
            st.info("Recognizing speech...")
            try:
                return recognizer.recognize_google(audio_data)
            except sr.RequestError:
                st.error("Error: Could not request results from Google Web Speech API")
                return ""
            except sr.UnknownValueError:
                st.error("Error: Could not understand the audio")
                return ""

    st.markdown(
        """
        <style>
        .centered-title {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
        }
        .centered-title h1 {
            margin: 0;
        }
        </style>

        """,
        unsafe_allow_html=True
    )

    with st.container():
        st.markdown('<div class="centered-title"><h2>AI-Powered Data Chatbot</h2></div>', unsafe_allow_html=True)

    file = st.sidebar.file_uploader("Upload your Data", type=["csv", "xlsx"])
    if file is not None:
        file_name, file_extension = os.path.splitext(file.name)
        dataset_name = file_name

        if file_extension == ".csv":
            data = pd.read_csv(file, encoding="latin-1")
            with open(file.name, "wb") as f:
                f.write(file.getbuffer())
            full_file_name = file.name
            CSV_FILE = full_file_name
            DB_FILE = file_name + ".db"

            def csv_to_sqlite(csv_file_path: str, sqlite_file: str, table_name: str) -> None:
                with sqlite3.connect(sqlite_file) as conn:
                    cursor = conn.cursor()

                    with open(csv_file_path, 'r', encoding='latin-1') as fin:
                        dr = csv.DictReader(fin)
                        headers = dr.fieldnames

                        # Check if headers exist
                        if not headers:
                            raise ValueError("No headers found in the CSV file.")

                        # Escape column names
                        escaped_headers = [f'"{header}"' for header in headers]
                        column_types = ['TEXT'] * len(headers)

                        # Drop table if it exists
                        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')

                        # Create table with escaped column names
                        columns_with_types = ", ".join(
                            [f"{header} {column_type}" for header, column_type in zip(escaped_headers, column_types)]
                        )
                        sql_create_table = f'CREATE TABLE "{table_name}" ({columns_with_types});'
                        cursor.execute(sql_create_table)

                        # Insert rows
                        placeholders = ', '.join(['?'] * len(headers))
                        sql_insert_data = f'INSERT INTO "{table_name}" VALUES ({placeholders});'

                        for row in dr:
                            cursor.execute(sql_insert_data, [row[header] for header in headers])
                        conn.commit()


            csv_to_sqlite(CSV_FILE, "Database.db", "My_table")

        elif file_extension == ".xlsx":
            data = pd.read_excel(file)
            full_file_name = f"{file_name}.csv"
            data.to_csv(full_file_name, index=False, encoding="utf-8-sig")
            CSV_FILE = full_file_name
            print(full_file_name)
            DB_FILE = file_name + ".db"

            def csv_to_sqlite(csv_file_path: str, sqlite_file: str, table_name: str) -> None:
                with sqlite3.connect(sqlite_file) as conn:
                    cursor = conn.cursor()
                    with open(csv_file_path, 'r', encoding='utf-8-sig') as fin:
                        dr = csv.DictReader(fin)
                        headers = dr.fieldnames
                        column_types = ['TEXT'] * len(headers)

                        cursor.execute(f"DROP TABLE IF EXISTS \"{table_name}\"")
                        columns_with_types = ", ".join(
                            [f"{header} {column_type}" for header, column_type in zip(headers, column_types)])
                        sql_create_table = f"CREATE TABLE \"{table_name}\" ({columns_with_types});"
                        cursor.execute(sql_create_table)

                        placeholders = ', '.join(['?'] * len(headers))
                        sql_insert_data = f"INSERT INTO \"{table_name}\" VALUES ({placeholders});"

                        for row in dr:
                            cursor.execute(sql_insert_data, [row[header] for header in headers])
                        conn.commit()

            csv_to_sqlite(CSV_FILE, "Database.db", "My_table")

        with st.expander("Click to show the data preview"):
            st.dataframe(data, hide_index=True)

    else:
        st.error("No file uploaded.")
        sys.exit()

    def clean_numeric_value(value):
        if isinstance(value, str):
            if re.match(r'^\d+K$', value, re.IGNORECASE):
                value = value[:-1] + '000'
            if re.match(r'^\d+(,\d{3})*$', value):
                value = value.replace(',', '')
        return value

    def infer_sqlite_type(column_values):
        data_type = 'TEXT'
        for value in column_values:
            cleaned_value = clean_numeric_value(value)
            try:
                int(cleaned_value)
                data_type = 'INTEGER'
            except ValueError:
                try:
                    float(cleaned_value)
                    data_type = 'REAL'
                except ValueError:
                    return 'TEXT'
        return data_type

    os.environ["OPENAI_API_KEY"] = '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'

    connectionString = 'sqlite:///Database.db'
    llm = OpenAI(temperature=0)
    db = SQLDatabase.from_uri(connectionString)
    dbChain = SQLDatabaseChain(llm=llm, database=db, verbose=True)

    static_question = "Write the theoretical summary of dataset in 5-6 lines"
    if 'summary_visible' not in st.session_state:
        st.session_state['summary_visible'] = False

    if st.button("Summary"):
        st.session_state['summary_visible'] = not st.session_state['summary_visible']
        if st.session_state['summary_visible']:
            static_output = dbChain.run(static_question)
            st.session_state['summary_output'] = static_output

    if st.session_state['summary_visible'] and 'summary_output' in st.session_state:
        st.write(st.session_state['summary_output'])

    if 'history' not in st.session_state:
        st.session_state['history'] = []

    if 'generated' not in st.session_state:
        st.session_state['generated'] = ["Hello! How can I help you?🔍"]

    if 'past' not in st.session_state:
        st.session_state['past'] = ["Hey! 👋"]

    if 'recognized_text' not in st.session_state:
        st.session_state['recognized_text'] = ""

    if 'show_questions' not in st.session_state:
        st.session_state['show_questions'] = False

    if 'tts_triggered' not in st.session_state:
        st.session_state['tts_triggered'] = [False] * len(st.session_state['generated'])

    # text_to_speech_enabled = st.sidebar.checkbox("Enable Text-to-Speech")

    if not os.path.exists("user_questions.xlsx"):
        df_questions = pd.DataFrame(columns=["Question"])
        df_questions.to_excel("user_questions.xlsx", index=False)

    if not os.path.exists("chatbot_data.xlsx"):
        df_chatbot_data = pd.DataFrame(columns=["Question", "Answer", "Feedback"])
        df_chatbot_data.to_excel("chatbot_data.xlsx", index=False)

    if not os.path.exists("feedback.xlsx"):
        df_feedback = pd.DataFrame(columns=["Name", "Suggestion"])
        df_feedback.to_excel("feedback.xlsx", index=False)

    def save_question_to_excel(question, dataset_name):

        df_questions = pd.read_excel("user_questions.xlsx")
        new_row = {"Question": question, "Dataset": dataset_name}
        df_questions = df_questions.append(new_row, ignore_index=True)
        df_questions.to_excel("user_questions.xlsx", index=False)



    def save_chatbot_data_to_excel(question, answer, feedback, dataset_name):
        df_chatbot_data = pd.read_excel("chatbot_data.xlsx")
        new_row = {"Question": question, "Answer": answer, "Feedback": feedback, "Dataset": dataset_name}
        df_chatbot_data = df_chatbot_data.append(new_row, ignore_index=True)
        df_chatbot_data.to_excel("chatbot_data.xlsx", index=False)

    def save_feedback_to_excel(name, suggestion):
        df_feedback = pd.read_excel("feedback.xlsx")
        new_row = {"Name": name, "Suggestion": suggestion}
        df_feedback = df_feedback.append(new_row, ignore_index=True)
        df_feedback.to_excel("feedback.xlsx", index=False)

    def display_previous_questions():
        df_questions = pd.read_excel("user_questions.xlsx")

        # Ensure the Dataset column exists
        if "Dataset" not in df_questions.columns:
            st.error("The Dataset column is missing in the user_questions.xlsx file.")
            return

        unique_datasets = df_questions["Dataset"].dropna().unique()
        if len(unique_datasets) == 0:
            st.write("No datasets available.")
            return

        selected_dataset = st.selectbox("Select a dataset:", unique_datasets)

        if selected_dataset:
            filtered_questions = df_questions[df_questions["Dataset"] == selected_dataset]
            filtered_questions = filtered_questions.tail(
                10)  # Display only the last 10 questions for the selected dataset

            st.write(f"Questions for dataset: **{selected_dataset}**")

            for index, row in filtered_questions.iterrows():
                question = row['Question']
                st.markdown(f"**Question:** {question}")

                # Add a "Get Answer" button below the question
                if st.button("Get Answer", key=f"get_answer_{index}"):
                    answer = fetch_answer(question)
                    st.write(f"**Answer:** {answer}")
                    st.session_state['past'].append(question)
                    st.session_state['generated'].append(answer)
                    st.session_state['tts_triggered'].append(False)

    # def display_previous_questions():
    #     df_questions = pd.read_excel("user_questions.xlsx")
    #
    #     # Ensure the Dataset column exists
    #     if "Dataset" not in df_questions.columns:
    #         st.error("The Dataset column is missing in the user_questions.xlsx file.")
    #         return
    #
    #     unique_datasets = df_questions["Dataset"].dropna().unique()
    #     if len(unique_datasets) == 0:
    #         st.write("No datasets available.")
    #         return
    #
    #     selected_dataset = st.selectbox("Select a dataset:", unique_datasets)
    #
    #     if selected_dataset:
    #         filtered_questions = df_questions[df_questions["Dataset"] == selected_dataset]
    #         filtered_questions = filtered_questions.tail(
    #             10)  # Display only the last 10 questions for the selected dataset
    #
    #         st.write(f"Questions for dataset: **{selected_dataset}**")
    #
    #         for index, row in filtered_questions.iterrows():
    #             question = row['Question']
    #             st.markdown(f"**Question:** {question}", unsafe_allow_html=True)
    #
    #             # Button to fetch answer for the question
    #             if st.button(f"Get answer for question {index}", key=f"get_answer_{index}"):
    #                 answer = fetch_answer(question)
    #                 st.write(f"**Answer:** {answer}")
    #                 st.session_state['past'].append(question)
    #                 st.session_state['generated'].append(answer)
    #                 st.session_state['tts_triggered'].append(False)

    # def display_previous_questions():
    #     df_questions = pd.read_excel("user_questions.xlsx")
    #     df_questions = df_questions.tail(10)  # Display only the last 10 questions
    #     st.write("Previously asked questions:")
    #
    #     for index, row in df_questions.iterrows():
    #         question = row['Question']
    #         st.markdown(f"**Question:** {question}", unsafe_allow_html=True)
    #         if st.button(f"Get answer for question ", key=f"get_answer_{index}"):
    #             answer = fetch_answer(question)
    #             st.write(f"**Answer:** {answer}")
    #             st.session_state['past'].append(question)
    #             st.session_state['generated'].append(answer)
    #             st.session_state['tts_triggered'].append(False)

    response_container = st.container()
    container = st.container()
    if st.button("Speak"):
        st.session_state['recognized_text'] = recognize_speech_from_mic()
        st.write(f"Recognized text: {st.session_state['recognized_text']}")

    with container:
        with st.form(key='my_form', clear_on_submit=True):
            user_input = st.text_input("Query:", value=st.session_state['recognized_text'],
                                       placeholder="Type your inquiry to query the dataset: 🔍", key='input')
            submit_button = st.form_submit_button(label='Send')



        if submit_button:
            user_input = st.session_state['recognized_text'] if st.session_state['recognized_text'] else user_input
            save_question_to_excel(user_input, dataset_name)
            output = dbChain.run(user_input)
            st.session_state['past'].append(user_input)
            st.session_state['generated'].append(output)
            st.session_state['recognized_text'] = ""
            st.session_state['tts_triggered'].append(False)

    if st.session_state['generated']:
        with response_container:
            for i in range(len(st.session_state['generated'])):
                display_message_with_avatar_and_voice(st.session_state["past"][i], is_user=True, index=i)
                display_message_with_avatar_and_voice(st.session_state["generated"][i], is_user=False, index=i)

                if st.button("🔊", key=f"read_answer_{i}"):
                    print(f"Read Answer {i} clicked")  # Debug statement
                    thread = threading.Thread(target=run_tts, args=(st.session_state["generated"][i],))
                    thread.start()
                    st.session_state['tts_triggered'][i] = True


                feedback = None
                feedback_buttons_container = st.container()
                with feedback_buttons_container:
                    col1, col2 = st.columns([1, 20])
                    with col1:
                        if st.button("👍", key=f"thumbs_up_{i}"):
                            feedback = "Positive"
                    with col2:
                        if st.button("👎", key=f"thumbs_down_{i}"):
                            feedback = "Negative"

                if feedback is not None:
                    save_chatbot_data_to_excel(st.session_state["past"][i], st.session_state["generated"][i], feedback,dataset_name)

    if st.button("Previously Asked Question"):
        st.session_state['show_questions'] = not st.session_state['show_questions']

    if st.session_state['show_questions']:
        display_previous_questions()

    if 'feedback_visible' not in st.session_state:
        st.session_state['feedback_visible'] = False

    if st.button("Provide Feedback"):
        st.session_state['feedback_visible'] = not st.session_state['feedback_visible']

    if st.session_state['feedback_visible']:
        with st.form(key='feedback_form', clear_on_submit=True):
            name = st.text_input("Name")
            suggestion = st.text_area("Suggestion")
            submit_feedback_button = st.form_submit_button(label='Submit Feedback')

        if submit_feedback_button:
            save_feedback_to_excel(name, suggestion)
            st.session_state['feedback_visible'] = False
            st.success("Feedback submitted successfully!")


if __name__ == "__main__":
    main()
