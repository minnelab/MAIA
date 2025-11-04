import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from loguru import logger


# Load the iris dataset
def load_iris():
    # Load the iris dataset
    iris = pd.read_csv('https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data', header=None)
    # Assign column names to the dataset
    iris.columns = ['sepal_length', 'sepal_width', 'petal_length', 'petal_width', 'species']
    # Assign numerical values to the species
    iris['species'] = iris['species'].map({'Iris-setosa': 0, 'Iris-versicolor': 1, 'Iris-virginica': 2})
    # Shuffle the dataset
    iris = iris.sample(frac=1).reset_index(drop=True)
    return iris

# Split the dataset into training and testing sets

def split_data(iris):
    # Assign the first 100 rows to the training set
    X_train = iris.iloc[:100, :-1].values
    y_train = iris.iloc[:100, -1].values
    # Assign the last 50 rows to the testing set
    X_test = iris.iloc[100:, :-1].values
    y_test = iris.iloc[100:, -1].values
    return X_train, y_train, X_test, y_test

# Normalize the dataset

def normalize_data(X_train, X_test):
    # Normalize the training and testing sets
    X_train = (X_train - np.mean(X_train, axis=0)) / np.std(X_train, axis=0)
    X_test = (X_test - np.mean(X_test, axis=0)) / np.std(X_test, axis=0)
    return X_train, X_test

# Train a Random Forest classifier
def train_classifier(X_train, y_train):
    # Train a Random Forest classifier
    clf = RandomForestClassifier(n_estimators=100, random_state=0)
    clf.fit(X_train, y_train)
    return clf


def main():
    # Load the iris dataset
    iris = load_iris()
    # Split the dataset into training and testing sets
    X_train, y_train, X_test, y_test = split_data(iris)
    # Normalize the dataset
    X_train, X_test = normalize_data(X_train, X_test)

    # Print the shapes of the training and testing sets
    logger.info(f'X_train shape: {X_train.shape}')
    logger.info(f'y_train shape: {y_train.shape}')
    logger.info(f'X_test shape: {X_test.shape}')
    logger.info(f'y_test shape: {y_test.shape}')

    # Train a Random Forest classifier
    clf = train_classifier(X_train, y_train)
    # Predict the species of the testing set
    y_pred = clf.predict(X_test)
    # Print the accuracy of the classifier
    accuracy = np.mean(y_pred == y_test)

    logger.info(f'Accuracy: {accuracy}')
    
if __name__ == '__main__':
    main()
