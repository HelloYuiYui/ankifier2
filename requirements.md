# Ankifier 2

This project aims to allow the user to streamline their Anki card creation pipeline. It is mainly aimed at turning words one may come across while consuming content in a target language into cloze cards with simple sentences using MistralAI API, turning the sentences MistralAI returns into audio files for listening comprehension and speaking production, and lastly adding these information to the user's Anki account into specified decks. 

## Structure 
1. A .csv file containing the target words, with each word in a single line. Words (or phrases) can appear in numerous formats, as the user may have differing amount of context for each word. Three most common possible ways (in French) are specified below:
    1. `boulangerie`: Given a specific word only, with no definite or indefinite article present. 
    2. `la glace/une glace`: Word with a definite or indefinite article. 
    3. `promener (verb)`: Word with function stated in parantheses, this is crucial for verbs and adjectives, especially more so for reflexive verbs, which may not always be given in a reflexive form. 
2. For each provided word, they should be sent to Mistral AI with a prompt, asking AI to present the top 3 most common senses of a word at most, and present a relatively simple sentence in the target language, along with its translation in English. Enforce this format through the prompt response field in the request. The sentences and the use of the given word in them should include important details such as the gender for nouns, and if it is a reflexive verb, the reflexive part. These important parts and the words should be hidden in the cloze format, with the word's sense/translation given as a hint to the user.
3. Once the example sentences are given, they should be passed to 11Labs AI for audio generation, and generated audio files should be kept at a specific folder. 
4. Once everything is sorted, the cards should be added to Anki in the following format: 
    Front: Example sentence in cloze format, hiding the word and other important information such as gender of reflexiveness, and hint as the translation/sense of the given word. 
    Back: Translation of the full sentence, and the pronunciation of the sentence shown in the front (so the target language one, to allow the user to repeat once the word and the translation is revealed)

## Tech Stack
- Python 3.14 from Homebrew
    - Poetry for package management 
- Mistral AI API for the AI agent 
- 11Labs API for audio generation 
- Ankiconnect for connecting to Anki 

## Coding Preferences 
Create a separate file for Mistral and 11Labs connectors, combine related functions (such as get_sentences, and get_audio) to these two in the utils/utils.py file. 