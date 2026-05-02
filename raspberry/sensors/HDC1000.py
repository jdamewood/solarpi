from SDL_Pi_HDC1000 import SDL_Pi_HDC1000

hdc1000 = SDL_Pi_HDC1000()
print("Temperature:", hdc1000.readTemperature())
print("Humidity:", hdc1000.readHumidity())

