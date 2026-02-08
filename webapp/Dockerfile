# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
# We copy it separately to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire webapp directory into the container
COPY . .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variables. These can be overridden in docker-compose.
# The webapp needs to know where the agent bureau's gateway is.
ENV GATEWAY_ADDRESS="http://bureau:9000/submit"

# Run webapp.py when the container launches
CMD ["python", "webapp.py"]
