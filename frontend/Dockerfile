# Use the official Python 3.10 image
FROM python:3.12

# Set the working directory
WORKDIR /app
# Coov the requirements file into the container
COPY . .
# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt
#Copv the rest of the application code into the
# Expose port 5000
EXPOSE 5000
# Set the environment variable for Flask

CMD ["python3","application.py"]