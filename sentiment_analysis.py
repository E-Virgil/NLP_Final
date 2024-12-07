import os
import re

import nltk
import pandas as pd
import torch
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def preprocess_text(text):
    # Lowercasing
    text = text.lower()

    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)

    # Tokenization
    words = nltk.word_tokenize(text)

    # Remove stop words
    stop_words = set(stopwords.words("english"))
    words = [w for w in words if not w in stop_words]

    words = [w for w in words if not w.isnumeric()]

    return " ".join(words)


def get_sentiment(text, tokenizer, model):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return torch.argmax(outputs.logits).item()


# Function to load and preprocess documents
def load_documents(directory):
    documents = []
    tickers = []
    filenames = []
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            with open(
                os.path.join(directory, filename),
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as f:
                text = f.read()
                documents.append(preprocess_text(text))
                tickers.append(filename[: filename.find("_")])
                filenames.append(filename)
    return documents, tickers, filenames


def get_sentiment_analysis(ticker):
    # Load your documents from a directory
    documents, tickers, filenames = load_documents("mda_texts")
    # Create TF-IDF vectorizer
    vectorizer = TfidfVectorizer()

    # Fit and transform the documents
    tfidf_matrix = vectorizer.fit_transform(documents)

    # Get feature names (words)
    feature_names = vectorizer.get_feature_names_out()

    # Access TF-IDF values for each document and term
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

    # Get sentiment for each document
    sentiments = []
    for text in documents:
        sentiment = get_sentiment(text, tokenizer, model)
        if sentiment == 0:
            sentiments.append("Negative")
        elif sentiment == 1:
            sentiments.append("Neutral")
        else:
            sentiments.append("Positive")

    # Combine results
    df = pd.DataFrame(
        {
            "Stock": tickers,
            "Filename": filenames,
            "Text": documents,
            "Sentiment": sentiments,
        }
    )

    return df.loc[df["Stock"] == ticker, ["Stock", "Sentiment"]]


if __name__ == "__main__":
    get_sentiment_analysis()
