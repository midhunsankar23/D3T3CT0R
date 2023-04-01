# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container to /app
WORKDIR /app

# Copy the requirements.txt file to the container
COPY requirements.txt .

# Install any necessary dependencies
RUN pip install  -r requirements.txt

# Copy the rest of the application code to the container
COPY . .

# Run the command to start the app
CMD ["python", "app.py"]