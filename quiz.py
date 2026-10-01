from datetime import datetime, timezone, UTC, timedelta
import random
from github import get_file, update_file, github_lock
from config import *
import math
from utils import today_string
from difflib import SequenceMatcher
import re


def normalize_answer(answer):
    answer = answer.casefold().strip()

    # Normalize punctuation to spaces
    answer = re.sub(r"[^a-z0-9\s]", " ", answer)

    # Collapse multiple spaces
    answer = re.sub(r"\s+", " ", answer)

    return answer


def answers_match(user_answer, correct_answer, threshold=0.85):
    user_answer = normalize_answer(user_answer)
    correct_answer = normalize_answer(correct_answer)

    # Exact match after normalization
    if user_answer == correct_answer:
        return True

    # Don't fuzzy-match very short answers
    if len(user_answer) < 5 or len(correct_answer) < 5:
        return False

    similarity = SequenceMatcher(
        None,
        user_answer,
        correct_answer
    ).ratio()

    return similarity >= threshold


# =========================
# QUIZ FUNCTIONS
# =========================

KEYS = [
    ["C", "A", 0, ["C", "D", "E", "F", "G", "A", "B"]],
    ["F", "D", -1, ["F", "G", "A", "Bb", "C", "D", "E"]],
    ["Bb", "G", -2, ["Bb", "C", "D", "Eb", "F", "G", "A"]],
    ["Eb", "C", -3, ["Eb", "F", "G", "Ab", "Bb", "C", "D"]],
    ["Ab", "F", -4, ["Ab", "Bb", "C", "Db", "Eb", "F", "G"]],
    ["Db", "Bb", -5, ["Db", "Eb", "F", "Gb", "Ab", "Bb", "C"]],
    ["Gb", "Eb", -6, ["Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"]],
    ["Cb", "Ab", -7, ["Cb", "Db", "Eb", "Fb", "Gb", "Ab", "Bb"]],

    ["G", "E", 1, ["G", "A", "B", "C", "D", "E", "F#"]],
    ["D", "B", 2, ["D", "E", "F#", "G", "A", "B", "C#"]],
    ["A", "F#", 3, ["A", "B", "C#", "D", "E", "F#", "G#"]],
    ["E", "C#", 4, ["E", "F#", "G#", "A", "B", "C#", "D#"]],
    ["B", "G#", 5, ["B", "C#", "D#", "E", "F#", "G#", "A#"]],
    ["F#", "D#", 6, ["F#", "G#", "A#", "B", "C#", "D#", "E#"]],
    ["C#", "A#", 7, ["C#", "D#", "E#", "F#", "G#", "A#", "B#"]]
]

MODES = [
    "Ionian",
    "Dorian",
    "Phrygian",
    "Lydian",
    "Mixolydian",
    "Aeolian",
    "Locrian"
]

QUESTION_TYPES = [
    ["major_minor",
    "minor_major",
    "major_accidental",
    "minor_accidental",
    "accidental_major",
    "accidental_minor"],
    ["mode_accidental",
    "accidental_mode"],
    ["transpose"],
    ["repertoire"]
]

TRANSPOSE_QUESTIONS = [
    {
        "image": "quizpics/sev1.jpg",
        "answer": "G#min7"
    },
    {
        "image": "quizpics/sev2.jpg",
        "answer": "Eb7"
    },
    {
        "image": "quizpics/sev3.jpg",
        "answer": "Fmaj7"
    },
    {
        "image": "quizpics/sev4.jpg",
        "answer": "Fdim7"
    },
    {
        "image": "quizpics/sev5.jpg",
        "answer": "Eb7"
    },
    {
        "image": "quizpics/sev6.jpg",
        "answer": "Gdim7"
    },
    {
        "image": "quizpics/sev7.jpg",
        "answer": "Amin7"
    },
    {
        "image": "quizpics/sev8.jpg",
        "answer": ["D#min7", "Ebmin7"]
    },
    {
        "image": "quizpics/sev9.jpg",
        "answer": "Fmin7"
    },
    {
        "image": "quizpics/sev10.jpg",
        "answer": "G#min7"
    },
    {
        "image": "quizpics/sev11.jpg",
        "answer": "A#dim7"
    },
    {
        "image": "quizpics/sev12.jpg",
        "answer": "C#7"
    },
    {
        "image": "quizpics/sev13.jpg",
        "answer": "Db7"
    },
    {
        "image": "quizpics/sev14.jpg",
        "answer": "Emaj7"
    },
    {
        "image": "quizpics/sev15.jpg",
        "answer": "Fbmaj7"
    },
    {
        "image": "quizpics/sev16.jpg",
        "answer": "G#maj7"
    },
    {
        "image": "quizpics/sev17.jpg",
        "answer": ["F#mM7","F#minM7"]
    },
    {
        "image": "quizpics/sev18.jpg",
        "answer": "Dmaj7"
    },
    {
        "image": "quizpics/sev19.jpg",
        "answer": "Fmin7"
    },
    {
        "image": "quizpics/sev20.jpg",
        "answer": "G#min7"
    }
    
]

def get_mode(key, mode_index):
    notes = key[3]

    return {
        "tonic": notes[mode_index],
        "mode": MODES[mode_index],
        "notes": notes[mode_index:] + notes[:mode_index],
        "accidentals": key[2]
    }


def get_question_type(user):
    quiz_stats = user.setdefault("quiz_stats", {})

    attempts = quiz_stats.setdefault("attempts", 0)
    correct = quiz_stats.setdefault("correct", 0)

    # Major/minor questions are always available
    question_types = QUESTION_TYPES[0].copy()

    # Unlock mode questions after:
    #   - at least 5 major/minor questions
    #   - at least 80% correct
    if attempts >= 5:
        accuracy = correct / attempts

        if attempts >= 20 and accuracy >= 0.90:
            question_types = QUESTION_TYPES[2].copy
        elif accuracy * math.log(attempts, 5) >= 0.90:
            question_types* = QUESTION_TYPES[1].copy()

    return random.choice(question_types)

def generate_question(question_type):
    """
    Generate a random quiz question.

    Returns:
        question       - question shown to user
        answer         - correct answer
        example        - example !answer command
        question_data  - information about the generated question
    """


    key_index = random.randrange(len(KEYS))
    key = KEYS[key_index]
    question_data = {
        "key_index": key_index
    }

    major = key[0]
    minor = key[1]
    accidentals = key[2]

    # -------------------------
    # Major / Minor questions
    # -------------------------

    if question_type == "major_minor":
        question = f"What is the relative minor of {major} major?"
        answer = minor
        example = f"!answer Ab or !answer c#"


    elif question_type == "minor_major":
        question = f"What is the relative major of {minor} minor?"
        answer = major
        example = f"!answer Ab or !answer c#"


    elif question_type == "major_accidental":
        question = (
            f"How many "
            f"{'sharps' if accidentals > 0 else 'flats'} "
            f"does {major} major have?"
        )
        answer = str(abs(accidentals))
        example = f"!answer 4"

    elif question_type == "minor_accidental":
        question = (
            f"How many "
            f"{'sharps' if accidentals > 0 else 'flats'} "
            f"does {minor} minor have?"
        )
        answer = str(abs(accidentals))
        example = f"!answer 4"

    elif question_type == "accidental_major":
        if accidentals == 0:
            question = "What major key has 0 accidentals?"
        else:
            accidental_name = "sharps" if accidentals > 0 else "flats"
            question = (
                f"What major key has {abs(accidentals)} "
                f"{accidental_name}?"
            )

        answer = major
        example = f"!answer Ab or !answer c#"


    elif question_type == "accidental_minor":
        if accidentals == 0:
            question = "What minor key has 0 accidentals?"
        else:
            accidental_name = "sharps" if accidentals > 0 else "flats"
            question = (
                f"What minor key has {abs(accidentals)} "
                f"{accidental_name}?"
            )

        answer = minor
        example = f"!answer Ab or !answer c#"


    # -------------------------
    # Mode questions
    # -------------------------

    elif question_type in ["mode_accidental", "accidental_mode"]:

        # Ionian through Locrian
        mode_index = random.randrange(7)

        modes = [
            "Ionian",
            "Dorian",
            "Phrygian",
            "Lydian",
            "Mixolydian",
            "Aeolian",
            "Locrian"
        ]

        mode = modes[mode_index]

        # The mode's tonic is the corresponding degree
        # of the major scale.
        mode_tonic = key[3][mode_index]

        if question_type == "mode_accidental":

            if accidentals == 0:
                question = (
                    f"How many sharps are in "
                    f"{mode_tonic} {mode}?"
                )
            else:
                accidental_name = (
                    "sharps" if accidentals > 0 else "flats"
                )

                question = (
                    f"How many {accidental_name} are in "
                    f"{mode_tonic} {mode}?"
                )

            answer = str(abs(accidentals))
            example = f"!answer 5"

        else:  # accidental_mode

            if accidentals == 0:
                question = (
                    f"Which {mode} scale has 0 flats?"
                )
            else:
                accidental_name = (
                    "sharps" if accidentals > 0 else "flats"
                )

                question = (
                    f"Which {mode} scale has "
                    f"{abs(accidentals)} {accidental_name}?"
                )

            answer = f"{mode_tonic}"
            example = f"!answer Ab or !answer c#"

        question_data = {
            "key_index": key_index,
            "mode_index": mode_index
        }

        return question, answer, example, question_data

    # -------------------------
    # Transpose questions
    # -------------------------   
    elif question_type in ["transpose"]:
        question_index = random.randrange(len(TRANSPOSE_QUESTIONS))
        transpose_question = TRANSPOSE_QUESTIONS[question_index]

        question = "In concert pitch, what chord is this?"
        answer = transpose_question["answer"]
        example = "G7, Dmaj7, Bbmin7, Fdim7, AminM7"

        question_data = {
            "type": "transpose",
            "index": question_index
            "attachment": transpose_question["image"]
        }

    else:
        raise ValueError(f"Unknown question type: {question_type}")

    return question, answer, example, question_data


def setup_quiz(bot):
    @bot.command()
    async def quiz(ctx):
        user_data, user_sha = get_file(USERS_URL)

        users = user_data.setdefault("users", {})
        user_id = str(ctx.author.id)

        if user_id not in users:
            await ctx.send("Use `!pull` first to initialize your account.")
            return

        user = users[user_id]
        today = today_string()

        # Initialize quiz statistics if they don't exist
        quiz_stats = user.setdefault("quiz_stats", {})
        quiz_stats.setdefault("attempts", 0)
        quiz_stats.setdefault("correct", 0)

        # Check whether the user already has today's quiz
        quiz = user.get("daily_quiz")

        if quiz is not None and quiz.get("date") == today:

            if quiz.get("completed"):
                await ctx.send("✅ You've already completed today's quiz.")
                return

            message = (
                f"**You already have today's quiz:**\n\n"
                f"{quiz['question']}\n\n"
                f"Reply using `!answer <answer>`.\n"
                f"Examples: {quiz['example']}"
            )

            # Re-send the image for transpose questions
            if quiz.get("type") == "transpose":
                transpose_question = TRANSPOSE_QUESTIONS[
                    quiz["question_data"]["index"]
                ]

                image_path = transpose_question["image"]
                image_url = QUIZ_MEDIA_URL + image_path

                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as response:
                        response.raise_for_status()
                        image_data = await response.read()

                file = discord.File(
                    io.BytesIO(image_data),
                    filename=os.path.basename(image_path)
                )

                await ctx.send(message, file=file)

            else:
                await ctx.send(message)

            return

        # Determine which type of question the user is eligible for
        question_type = get_question_type(user)

        # Generate the question
        question, answer, example, question_data = generate_question(
            question_type
        )

        # Store the quiz
        user["daily_quiz"] = {
            "date": today,
            "type": question_type,
            "question": question,
            "answer": answer,
            "example": example,
            "question_data": question_data,
            "completed": False
        }

        update_file(USERS_URL, user_data, user_sha)

        message = (
            f"**Daily Music Theory Quiz**\n\n"
            f"{question}\n\n"
            f"Reply using `!answer <answer>`.\n"
            f"Examples: {example}"
        )

        # Send image for transpose questions
        if question_type == "transpose":
            transpose_question = TRANSPOSE_QUESTIONS[
                question_data["index"]
            ]

            image_path = transpose_question["image"]
            image_url = QUIZ_MEDIA_URL + image_path

            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    response.raise_for_status()
                    image_data = await response.read()

            file = discord.File(
                io.BytesIO(image_data),
                filename=os.path.basename(image_path)
            )

            await ctx.send(message, file=file)

        else:
            await ctx.send(message)


    @bot.command()
    async def answer(ctx, *, response):
        user_data, user_sha = get_file(USERS_URL)

        users = user_data.setdefault("users", {})
        user_id = str(ctx.author.id)

        if user_id not in users:
            await ctx.send("Use `!pull` first to initialize your account.")
            return

        user = users[user_id]

        quiz = user.get("daily_quiz")

        if quiz is None or quiz.get("date") != today_string():
            await ctx.send(
                "You don't have today's quiz.\n"
                "Use `!quiz` first."
            )
            return

        if quiz.get("completed"):
            await ctx.send("You've already completed today's quiz.")
            return

        # Initialize quiz statistics
        quiz_stats = user.setdefault("quiz_stats", {})
        quiz_stats.setdefault("attempts", 0)
        quiz_stats.setdefault("correct", 0)

        if isinstance(correct_answer, list):
            correct_answers = [str(answer).strip().lower() for answer in correct_answer]
            answer_string = " or ".join(correct_answer)
        else:
            correct_answers = [str(correct_answer).strip().lower()]
            answer_string = correct_answer

        user_answer = response.strip().lower()

        # Check answer
        quiz_stats["attempts"] += 1
        quiz["completed"] = True
        if user_answer in correct_answers:
            quiz_stats["correct"] += 1
            user["coins"] = user.get("coins", 0) + 1

            update_file(USERS_URL, user_data, user_sha)

            await ctx.send(
                f"Correct!\n"
                f"You earned **1 WMGpeSO**.\n"
                f"You now have {user['coins']}."
            )

        else:
            update_file(USERS_URL, user_data, user_sha)
            await ctx.send(
                f"Incorrect.\n"
                f"The correct answer was **{answer_string}**."
            )

