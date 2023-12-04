from flask import Flask, render_template, request, jsonify
import sys
import json
from openai import OpenAI
import requests
import random
import time
import subprocess
import pandas as pd
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
import nltk
from nltk.corpus import stopwords
import numpy
import tensorflow
import random
import json
from keras.preprocessing.text import Tokenizer, tokenizer_from_json 
from keras_preprocessing.sequence import pad_sequences
from numpy import asarray
from numpy import zeros
from keras.models import Sequential
from tensorflow.keras.utils import to_categorical
from keras.models import Sequential
from tensorflow.keras.layers import Embedding, Flatten, Dense, Dropout
import pickle
from keras.models import load_model
import spacy
nlp = spacy.load('en_core_web_md')
import re
import numpy as np
from nltk.corpus import stopwords
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.models import load_model






train_model_bool = False
file_name_model = 'DNN_model_final.h5'
dev_mode=False
examples_length=100
num_examples = 10










with open('parte_slop.json', encoding='utf-8') as file:
    Paises = json.load(file)

city_names = list(Paises.keys())  # Extract city names into a list
descriptions = list(Paises.values())  # Extract descriptions into a list

#print(city_names)
#print(descriptions)

nltk.download('stopwords')
stopwords_list = list(set(stopwords.words('english')))
CV = CountVectorizer(stop_words=stopwords_list)
# Inicializar el vectorizador
#CV = CountVectorizer() #connvierte una loista en una descripcion numerica
# Convertir el arreglo de descripciones en un modelo de Textos Vs Vocabulario
#Toma la lista y la vuelve en una matriz numerica y los valores de la matriz indican la frecuencia de cada palabra
VectorPalabras = CV.fit_transform(descriptions)

# Forma del vector resultante (Textos, Vocabulario)
print("Forma del vector(Textos, Vocabulario) = " + str(VectorPalabras.shape))

# Creamos un transformador de nuestro vector
tfidf_transformer = TfidfTransformer(use_idf=True) #instancia de un transformador que le decimos que va a usar idf
tfidf_transformer.fit(VectorPalabras)#saca el idf (mide exclusividad) y tf (mide frecuencia)

# Insertamos los valores en un DataSet
df_idf = pd.DataFrame(tfidf_transformer.idf_, index = CV.get_feature_names_out(), columns = ["Pesos-IDF"])
# Ordenams los valores del de menor relevancia hasta el de mayor relevancia
df_idf.sort_values(by=['Pesos-IDF'])

# Creamos el "count vector" el cuál indica la cantidad de
# veces que se repite cada token único
count_vector = CV.transform(descriptions)

# Cálculo de los valores para tf-idf, es decir le da la relevancia a cada palabra
tf_idf_vector = tfidf_transformer.transform(count_vector)

# Generamos un DataFrame con los valores tf-idf de cada token
# para cada texto
df = pd.DataFrame(tf_idf_vector.T.todense(),
                  index = CV.get_feature_names_out(),
                  columns = city_names)

#Sacar los valores mas relevantes de cada columna y almacenarlos en un diccionario
top_words_by_city = {}

for city in city_names:
    # Sort the DataFrame column (city) by TF-IDF values to get top words
    top_words_by_city[city] = df[city].nlargest(examples_length).index.tolist()

# Display or further process the top words for each city
for city, top_words in top_words_by_city.items():
    print(f"Top words for {city}: {', '.join(top_words)}")

#words_per_example = 100
examples_by_city ={}

for city, top_words in top_words_by_city.items():
    #print(f"Examples for {city}:")
    examples = []
    for _ in range(num_examples):
        # Randomly select a few words from the top words list for the city
        num_words_in_sentence = examples_length
        selected_words = top_words.copy()
        random.shuffle(selected_words)

        # Create an example sentence using the selected words
        example_sentence = ' '.join(selected_words)
        examples.append(example_sentence.lower())
    examples_by_city[city] = examples
    #print(f"Generated {num_examples} examples for {city}.")
    #print(examples_by_city['Bangkok'])

Y_Examples = list()

for city, examples in examples_by_city.items():
    for ex in examples:
        Y_Examples.append(list(examples_by_city.keys()).index(city))
print("Vector de salidas Y para Examples by city")
print(str(Y_Examples))

X_Examples = list()
for lista in examples_by_city.values():
    for texto in lista:
        X_Examples.append(texto)
#print(X_Examples)

#Generar la matriz de entrada
tokenizer_path = 'tokenizer_'+file_name_model.split('.')[0]+'.pkl'
maxlen = examples_length
tokenizer_Examples=None
if(train_model_bool):
    tokenizer_Examples = Tokenizer(num_words=10000)
    tokenizer_Examples.fit_on_texts(X_Examples)
    tokenizer_json = tokenizer_Examples.to_json()
    with open(tokenizer_path, 'w', encoding='utf-8') as f:
        f.write(tokenizer_json)
else:
    # Load the tokenizer
    with open(tokenizer_path, 'r', encoding='utf-8') as f:
        loaded_tokenizer_json = f.read()
        tokenizer_Examples = tokenizer_from_json(loaded_tokenizer_json)

X_Examples_Tok = tokenizer_Examples.texts_to_sequences(X_Examples)
X_Examples_train = pad_sequences(X_Examples_Tok, padding='post', maxlen=maxlen)
print("Matriz de entrada para Examples:")
print(X_Examples_train)

# Asignamos los embeddings correspondientes a cada matriz
# con la que se entrenarán los modelos por medio de un método

# Asignamos los embeddings correspondientes a cada matriz
# con la que se entrenarán los modelos por medio de un método
def Asignar_Embeddings(tokenizer, vocab_size):
    # Generamos la matriz de embeddings (Con 300 Características)
    embedding_matrix = zeros((vocab_size, 300))
    for word, index in tokenizer.word_index.items():
        # Extraemos el vector de embedding para cada palabra
        embedding_vector = nlp(word).vector
        # Si la palbra si existía en el vocabulario
        # agregamos su vector de embeddings en la matriz
        if embedding_vector is not None:
            embedding_matrix[index] = embedding_vector
    return embedding_matrix

vocab_size_Examples = len(tokenizer_Examples.word_index) + 1
embedding_matrix_Examples = Asignar_Embeddings(tokenizer_Examples, vocab_size_Examples)



# Definición del método para tener la arquitectura de los modelos para cada nivel contextual
def Definir_Modelos_LSTM(vocab_size, embedding_matrix, X_train, labels):
    model = Sequential()
    embedding_layer = Embedding(vocab_size, 300, weights=[embedding_matrix], input_length=X_train.shape[1], trainable=False)
    model.add(embedding_layer)
    #model.add(DNN(20, dropout=0.2, recurrent_dropout=0.2))
    model.add(Flatten())
    model.add(Dense(len(labels), activation='softmax'))  # Change 'relu' to 'softmax' for classification

    model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

    print(model.summary())
    print("\nPalabras en el vocabulario:")
    print(vocab_size)
    return model

def Definir_Modelos_DNN(vocab_size, embedding_matrix, X_train, labels):
    model = Sequential()
    embedding_layer = Embedding(vocab_size, 300, weights=[embedding_matrix], input_length=X_train.shape[1], trainable=False)
    model.add(embedding_layer)

    model.add(Dense(len(labels), activation='relu'))  # You can adjust the activation function as needed
    # Add dropout layer
    model.add(Dropout(0.1))

    model.add(Flatten())
    model.add(Dense(len(labels), activation='softmax'))

    model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

    print(model.summary())
    print("\nPalabras en el vocabulario:")
    print(vocab_size)
    return model

# Generamos la arquitectura para el modelo de N1
model_Examples = None
if(train_model_bool):
    model_Examples = Definir_Modelos_DNN(vocab_size_Examples, embedding_matrix_Examples, X_Examples_train, examples_by_city.keys())
else:
    with open('./'+file_name_model, 'rb') as file:
        model_Examples = load_model(file_name_model)


def Entrenar_Modelos(X_train, Y, model, labels):
    #Y = np.array(Y)

    # Declaramos librería para convertir la salida en un vector
    # de X elementos con activación en la columna correspondiente
    # a su categoría
    train_labels = to_categorical(Y, num_classes=len(labels))
    print('Matriz de salidas')
    print(train_labels)


    # Ajuste de los datos de entrenamiento al modelo creado
    history = model.fit(X_train, train_labels, epochs=25,  batch_size=1, verbose=1)

    # Cálculo de los procentajes de Eficiencia y pérdida
    score = model.evaluate(X_train, train_labels, verbose=1)
    print("\nTest Loss:", score[0])
    print("Test Accuracy:", score[1])
    return history

# Entrenamos el modelo del nivel NI y obtenemos el historial de las épocas para realizar su gráfica
history_Examples = None
if(train_model_bool):
    history_Examples = Entrenar_Modelos(X_Examples_train, Y_Examples, model_Examples, examples_by_city.keys())
    # Load the model
    model_Examples.save(file_name_model)

# Now you can use `loaded_model` for predictions or further training



































































def getCities(input_text):
    # Remove all non-alphanumeric characters
    input_text = re.sub(r'[^a-zA-Z0-9\s]', '', input_text)

    # Remove stopwords using NLTK
    stop_words = set(stopwords.words('english'))
    words = input_text.split()
    filtered_words = [word for word in words if word.lower() not in stop_words]
    input_text = ' '.join(filtered_words)

    # Tokenize the text
    sequences = tokenizer_Examples.texts_to_sequences([input_text])

    # Custom padding function to repeat words until there are 100 encoded words
    def custom_padding(sequences, maxlen=examples_length):
        padded_sequences = []
        for sequence in sequences:
            while len(sequence) < maxlen:
                sequence = sequence + sequence
            padded_sequences.append(sequence[:maxlen])
        return padded_sequences
    padded_sequences = custom_padding(sequences)
    #padded_sequences = pad_sequences(sequences, padding='post', maxlen=examples_length)

    print(padded_sequences)
    # Load the pre-trained model
    model = model_Examples  # Replace with the actual model file name

    # Predict using the model
    predictions = model.predict(np.array(padded_sequences))
    print('prediction result: ')
    print(str(predictions))
    # Get the top 5 neurons
    top_neurons = np.argsort(predictions[0])[-5:][::-1]

    # Return the top 5 cities
    top_cities = [city_names[index] for index in top_neurons]
    return top_cities



#list of cities to link the neuron number to city
def getCitiesFake(text):
    #load pickle
    #predict with model with text
    #get top 5 neurons
    #create result_list with cities_list[neuron1,neuron2,neuron3,neuron4,neuron5]
    #return result_list

    return ['New York','Amsterdam','Rome','London','Madrid']

app = Flask(__name__)
client = None
client = OpenAI(
    api_key="My API Key",
)
gloabl_input=[""]

time_entities = {
    "season": {
      "summer": "2024-06-21",
      "winter": "2023-12-21",
      "spring": "2024-03-21",
      "fall": "2024-09-24"
    },
    "month": {
      "january": "2024-01-01",
      "february": "2024-02-01",
      "march": "2024-03-01",
      "april": "2024-04-01",
      "may": "2024-05-01",
      "june": "2024-06-01",
      "july": "2024-07-01",
      "august": "2024-08-01",
      "september": "2024-09-01",
      "october": "2024-10-01",
      "november": "2024-11-01",
      "december": "2023-12-01"
    },
    "holiday": {
      "spring break": "2024-03-15",
      "summer break": "2024-06-15",
      "spring vacation": "2024-03-15",
      "summer vacation": "2024-06-15",
      "christmas": "2023-12-25",
      "new year": "2024-01-01",
      "easter": "2024-04-15",
      "thanksgiving": "2024-11-23",
      "halloween": "2024-10-31",
      "independence day": "2024-07-04",
      "labor day": "2024-09-04",
      "memorial day": "2024-05-29",
      "hanukkah": "2023-12-13",
      "diwali": "2024-11-06",
      "eid al-fitr": "2024-05-27",
      "eid al-adha": "2024-07-20",
      "valentine's day": "2024-02-14",
      "mother's day": "2024-05-14",
      "father's day": "2024-06-18",
    }
  }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/result', methods=['GET'])
def result():
    try:
        cities_param = request.args.get('cities')

        cities = json.loads(cities_param)

        return render_template('result.html', cities=cities)
    except Exception as e:
        return str(e), 400

@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.get_json()
        input_text = data.get('input')
        gloabl_input[0] = input_text

        result = getCities(input_text)

        return jsonify(result=result)
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route('/get_image/<city>')
def get_unsplash_image(city):
    temp_url='https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Placeholder_view_vector.svg/310px-Placeholder_view_vector.svg.png'
    if(dev_mode):
        return jsonify({'image_url': temp_url}) #comment for prodcution
    access_key = '7iU8pHx9ol-FJexwDVFIgdhMpO-wxKVNk9tbKovW8PU'
    base_url = 'https://api.unsplash.com/search/photos/'
    params = {
        'query': city,
        'client_id': access_key,
    }

    try:
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and 'results' in data and data['results']:
                random_index = random.randint(0, len(data['results']) - 1)

                image_url = data['results'][random_index]['urls']['small']
                return jsonify({'image_url': image_url})
            else:
                return jsonify({'error': 'No results found'}), 404
        else:
            return jsonify({'error': f'Request failed with status code {response.status_code}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/reason-to-go/', methods=['POST'])
def get_gpt_reason():
    temp =  "sd asndjafskn akjf skndf dnf dsdn fdskn fdskn fkf dskf dsnf dsknf dsknf dsfk sknds fkdsf sknf sdknf dsnf dsknf dskf dsfknds flsd fns fkds fdsknf dskfn dsfknds fkds fkdsnf dskf dsknfds fks fdsknf dsknf dsknf dskf dskf dsknf fkds fks frekg trkn hknyt hkyth ylj yl jytpkhrkgepf wfow dqk dad 2o3 43kr f f foe flkf el feb grv ekv eovfe voefvke v e."
    
    if(dev_mode):
        time.sleep(5) #comment for production
        return jsonify({'generated_reason': temp}) #comment for production
    try:
        data = request.get_json()
        input_text = gloabl_input[0]
        city = data.get('city', '')

        if not input_text or not city:
            return jsonify({'error': 'Both "input" and "city" parameters are required.'}), 400

        prompt = f'In a maximum of 60 words tell me why {city} is a good place to go given a person is looking for a place to vacation and this is their input: {input_text}'

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="gpt-3.5-turbo",
            max_tokens=100
        )
        generated_reason = chat_completion.choices[0].message.content

        return jsonify({'generated_reason': generated_reason})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-date', methods=['GET'])
def getDate(): #Reconocimiento de entidades de tiempo para fechas de vuelos
    try:
        if global_input:
            input_text = global_input[0].lower()
            for entity_type, entities in time_entities.items():
                for entity in entities:
                    if entity in input_text:
                        return time_entities[entity_type][entity]
        return "2024-01-01"
    except Exception as e:
        return "2024-01-01"



    
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python app.py <key_file_path>")
        sys.exit(1)

    key_file_path = sys.argv[1]

    try:
        with open(key_file_path, 'r') as key_file:
            openai_key = key_file.read().strip()
            client = OpenAI(
                api_key=openai_key,
            )
    except FileNotFoundError:
        print(f"Error: Key file not found at {key_file_path}")
        sys.exit(1)

    # Use the openai_key as needed in your application
    print(f"Using OpenAI key from {key_file_path}: {openai_key}")
    app.run(host='0.0.0.0',port=3003)

    