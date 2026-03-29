
import io
import openai
import json
import os
from decimal import Decimal
import time
from PIL import Image
import requests
from nutriapp import settings


API_KEY = settings.OPENAI_API_KEY
openai.api_key = API_KEY
os.environ["GRPC_DEFAULT_TIMEOUT"] = "60"

def query_openai_(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Using GPT-3.5 Turbo
                messages=[{"role": "user", "content": prompt}],
                timeout=60
            )
            if response and "choices" in response and len(response["choices"]) > 0:
                candidate_text = response["choices"][0]["message"]["content"].strip()
                
                if candidate_text.startswith("```json") and candidate_text.endswith("```"):
                    candidate_text = candidate_text[7:-3].strip()
                
                return candidate_text
            else:
                print(f"Empty response on attempt {attempt + 1}. Retrying...")
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}. Retrying...")
        time.sleep(2)
    raise Exception("Failed to get a valid response after multiple attempts.")

def create_activity_prompt_(activity_name, duration_minutes):
    return f"""
    You are an expert fitness tracker. Calculate the calories burned for the following activity:
    **Activity Details:**
    - Activity Name: {activity_name}
    - Duration: {duration_minutes} minutes
    **Rules and Formulas:**
    1. Standard Calorie Burn Rates (per minute):
       - Running: 10 kcal/min
       - Swimming: 8 kcal/min
       - Dancing: 6 kcal/min
       - Football: 7 kcal/min
       - Baseball: 5 kcal/min
       - Other Activities: Use an average of 6 kcal/min if no specific rate is available.
    2. Total Calories Burned:
       - Formula: Total Calories Burned = Calories Burned per Minute × Duration in Minutes
    3. Daily Log:
       - Add the activity to the daily log and calculate the total calories burned for the day.
    **Output Format:**
    Provide the output in JSON format:
    {{
        "ActivityName": "{activity_name}",
        "DurationMinutes": {duration_minutes},
        "CaloriesBurnedPerMinute": X,
        "TotalCaloriesBurned": Y
    }}
    Ensure there are no additional messages or formatting. Just return the JSON.
    """

def calculate_calorie_burned_locally(activity_name, duration_minutes):
    standard_rates = {
        "Running": 10,
        "Swimming": 8,
        "Dancing": 6,
        "Football": 7,
        "Baseball": 5,
    }
    default_rate = 6   
    calories_per_minute = standard_rates.get(activity_name, default_rate)
    
    return calories_per_minute   

def calculate_calorie_burned(activity_name, duration_minutes):
    prompt = create_activity_prompt_(activity_name, duration_minutes)

    try:
        openai_response = query_openai_(prompt)
        parsed_response = json.loads(openai_response)
        calories_per_minute = parsed_response["CaloriesBurnedPerMinute"]
    except Exception as e:
        # Fallback to local calculation in case of errors.
        print(f"Error: {e}. Falling back to local calculations.")
        calories_per_minute = calculate_calorie_burned_locally(activity_name, duration_minutes)

    return calories_per_minute

#=============================== Develop Plan =============================================

def query_openai(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Using GPT-3.5 Turbo
                messages=[{"role": "user", "content": prompt}],
                timeout=60
            )
            candidate_text = response["choices"][0]["message"]["content"].strip()
            if candidate_text:
                return candidate_text
            else:
                print(f"Empty response on attempt {attempt + 1}. Retrying...")
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}. Retrying...")
        time.sleep(2)
    raise Exception("Failed to get a valid response after multiple attempts.")

def calculate_health_score(bmi, workouts_per_week, age):
    if bmi < 18.5:
        bmi_score = 3
    elif bmi <= 24.9:
        bmi_score = 8
    elif bmi <= 29.9:
        bmi_score = 5
    else:
        bmi_score = 2

    if workouts_per_week == "RestandRecovery":
        activity_score = 2
    elif workouts_per_week == "Lite":
        activity_score = 5
    elif workouts_per_week == "Moderate":
        activity_score = 7
    elif workouts_per_week == "Heavy":
        activity_score = 9
    else:
        raise ValueError("Invalid activity level. Please specify 'Rest and Recovery', 'Lite', 'Moderate', or 'Heavy'.")

    if age < 30:
        age_score = 8
    elif age <= 50:
        age_score = 6
    else:
        age_score = 4

    total_score = (bmi_score + activity_score + age_score) / 3
    health_score = round(total_score, 1)
    return health_score

def calculate_nutrition_locally(gender, height, current_weight, age, workouts_per_week, goal, desired_weight, diet_type, obstacle, speed):
    bmi = current_weight / ((height / 100) ** 2)    
    health_score = calculate_health_score(bmi, workouts_per_week, age)
    
    if gender.lower() == "male":
        bmr = 88.362 + (13.397 * current_weight) + (4.799 * height) - (5.677 * age)
    elif gender.lower() == "female":
        bmr = 447.593 + (9.247 * current_weight) + (3.098 * height) - (4.330 * age)
    else:
        raise ValueError("Invalid gender. Please specify 'male' or 'female'.")
    
    if workouts_per_week == "RestandRecovery":
        activity_factor = 1.00   
    elif workouts_per_week == "Lite":
        activity_factor = 1.2  
    elif workouts_per_week == "Moderate":
        activity_factor = 1.3   
    elif workouts_per_week == "Heavy":
        activity_factor = 1.5 
    else:
        raise ValueError("Invalid activity level. Please specify 'Rest and Recovery', 'Lite', 'Moderate', or 'Heavy'.")
    
    tdee = bmr * activity_factor
    if goal.lower() == "lose":
        daily_calories = tdee - 500   
    elif goal.lower() == "maintain":
        daily_calories = tdee
    elif goal.lower() == "gain":
        daily_calories = tdee + 500  
    else:
        daily_calories = tdee 
    
    def get_macronutrient_ratios(diet_type):
        if diet_type.lower() == "balanced":
            carbs_ratio, protein_ratio, fats_ratio = 0.55, 0.3, 0.15
        elif diet_type.lower() == "pescatarian":
            carbs_ratio, protein_ratio, fats_ratio = 0.45, 0.3, 0.25
        elif diet_type.lower() == "vegetarian":
            carbs_ratio, protein_ratio, fats_ratio = 0.45, 0.3, 0.25
        elif diet_type.lower() == "vegan":
            carbs_ratio, protein_ratio, fats_ratio = 0.55, 0.25, 0.2
        else:
            carbs_ratio, protein_ratio, fats_ratio = 0.5, 0.3, 0.2
        
        return carbs_ratio, protein_ratio, fats_ratio
    
    carbs_ratio, protein_ratio, fats_ratio = get_macronutrient_ratios(diet_type)
    carbs = round((daily_calories * carbs_ratio) / 4)   
    protein = round((daily_calories * protein_ratio) / 4)   
    fats = round((daily_calories * fats_ratio) / 9)   
    
    if speed.lower() == "slow":
        weekly_weight_change_rate = 0.25  # Slow: 0.25 kg/week
    elif speed.lower() == "normal":
        weekly_weight_change_rate = 0.5  # Normal: 0.5 kg/week
    elif speed.lower() == "fast":
        weekly_weight_change_rate = 0.75  # Fast: 0.75 kg/week
    else:
        raise ValueError("Invalid speed. Please specify 'Slow', 'Normal', or 'Fast'.")
    
    weight_difference = abs(desired_weight - current_weight)
    weeks_to_goal = round(weight_difference / weekly_weight_change_rate)
    
    return {
        "DailyCalories": round(daily_calories),
        "Carbs": carbs,
        "Protein": protein,
        "Fats": fats,
        "WeeksToGoal": weeks_to_goal,
        "HealthScore": health_score,
    }

def create_nutrition_prompt(gender, height, current_weight, age, workouts_per_week, goal, desired_weight, diet_type, obstacle, speed):
    prompt = f"""
    Calculate daily nutritional data based on the following user input:
    Gender: {gender}
    Height: {height} cm
    Current Weight: {current_weight} kg
    Desired Weight: {desired_weight} kg
    Age: {age} years
    Workouts per week: {workouts_per_week}
    Goal: {goal}
    Type of Diet: {diet_type}
    What's holding you back: {obstacle}
    Speed to reach target: {speed}
    Weekly weight change rate: 
       - Slow: 0.25 kg/week
       - Normal: 0.5 kg/week
       - Fast: 0.75 kg/week
    Perform the following calculations step-by-step:
    1. Calculate Basal Metabolic Rate (BMR) using the Harris-Benedict formula:
       - For males: BMR = 88.362 + (13.397 × weight in kg) + (4.799 × height in cm) - (5.677 × age)
       - For females: BMR = 447.593 + (9.247 × weight in kg) + (3.098 × height in cm) - (4.330 × age)
    2. Adjust BMR for activity level to calculate Total Daily Energy Expenditure (TDEE):
       - Rest and Recovery: TDEE = BMR × 1.00
       - Lite: TDEE = BMR × 1.2
       - Moderate: TDEE = BMR × 1.3
       - Heavy: TDEE = BMR × 1.5
    3. Adjust TDEE based on the goal and weekly weight change rate:
       - To gain/lose 1 kg per week, adjust calories by ±7700 kcal per week (±1100 kcal per day).
    4. Break down macronutrients into grams:
       - Carbs: 50% of total calories / 4
       - Protein: 30% of total calories / 4
       - Fats: 20% of total calories / 9
    Provide the output in JSON format:
    {{
        "DailyCalories": X,
        "Carbs": Y,
        "Protein": Z,
        "Fats": W,
        "WeeksToGoal": N,
        "HealthScore": S
    }}
    without any additional messages or formatting. Don't add any space or indentation or anything
    """
    return prompt


def develop_plan_ai(gender, height, current_weight, age, workouts_per_week, goal, desired_weight, diet_type, obstacle, speed):
    bmi = current_weight / ((height / 100) ** 2)
    prompt = create_nutrition_prompt(
        gender, height, current_weight, age, workouts_per_week, goal, desired_weight, diet_type, obstacle, speed
    )

    try:
        openai_response = query_openai(prompt)
        parsed_response = json.loads(openai_response)
        parsed_response["HealthScore"] = calculate_health_score(bmi, workouts_per_week, age)
    except Exception as e:
        print(f"Failed to parse OpenAI response: {e}. Falling back to local calculations.")
        parsed_response = calculate_nutrition_locally(
            gender, height, current_weight, age, workouts_per_week, goal, desired_weight, diet_type, obstacle, speed
        )

    return json.dumps(parsed_response, indent=2)

#=============================== Adjust Goal =============================

def adjust_goal_calculate(fat=0, carbohydrate=0, protein=0, calories=0):
    f = fat
    c = carbohydrate
    p = protein
    print(f, c, p, "-----------------------------------------------------------------------------------------------------------------")
    fat = float(fat)
    carbohydrate = float(carbohydrate)
    protein = float(protein)
    calories = float(calories)
    

    if f:
        fat_calories = float(fat * 9)
        remaining_calories = float(calories - fat_calories)
        carbohydrate = float((remaining_calories * 0.50) / 4)  
        protein = float((remaining_calories * 0.30 )/ 4)  
    elif c:
        carb_calories = carbohydrate 
        remaining_calories = calories - carb_calories
        fat = remaining_calories * 0.20 / 9   
        protein = remaining_calories * 0.30 / 4   
    elif p:
        protein_calories = protein 
        remaining_calories = calories - protein_calories
        fat = remaining_calories * float(0.20) / 9  
        carbohydrate = remaining_calories * float(0.50) / 4  
    else:
        return False
    
    if fat and carbohydrate and protein:
        result = {
            "carbohydrate": Decimal(carbohydrate), 
            "protein": Decimal(protein), 
            "fat": Decimal(fat)
        }
        return result
    else:
        return False
    
#----------------------------------------------------------------------------


def infer_element_values(fe_value, zn_value):
    """
    This function takes the values of Fe and Zn, and returns inferred values
    for other elements (Cu, Mn, Se, I, Cr, Mo, F, Co) based on some form of logic.
    This is a placeholder logic to demonstrate how the values might be inferred.
    """
    print(type(fe_value), "---------------------------------")

    
    # Simulating some form of relationship or calculation between Fe, Zn and other elements
    # In this case, we are just generating random values to represent these outputs for demonstration.
    cu_value = fe_value * 0.8 + zn_value * 0.5  # Example logic: some combination of Fe and Zn
    mn_value = fe_value * 0.9 + zn_value * 0.3
    se_value = zn_value * 1.2
    i_value = zn_value * 0.7
    cr_value = fe_value * 1.1
    mo_value = zn_value * 1.5
    f_value = fe_value * 0.4
    co_value = fe_value * 0.6 + zn_value * 0.8
    
    # Returning all the inferred values in a dictionary
    return {
        "Cu": cu_value,
        "Mn": mn_value,
        "Se": se_value,
        "I": i_value,
        "Cr":cr_value,
        "Mo": mo_value,
        "F": f_value,
        "Co": co_value,
    }

# # Example values for Fe and Zn (can be replaced by actual values)
# fe_input = 50  # Example value for Fe
# zn_input = 30  # Example value for Zn

# # Getting the inferred values for the other elements
# output_values = infer_element_values(fe_input, zn_input)

# # Printing the results
# for element, value in output_values.items():
#     print(f"{element}: {value}")




#======================= generate_food_name ===================


import base64  


openai.api_key = API_KEY

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def generate_food_name(image_file):
    try:
        # Read and encode image (from InMemoryUploadedFile or path)
        if hasattr(image_file, 'read'):  # Django file
            image_bytes = image_file.read()
        else:  # path
            with open(image_file, 'rb') as f:
                image_bytes = f.read()

        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Use updated GPT-4 Turbo with vision support
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Identify the food item in this image. If it's a known food, return its name only. If nothing is found, return '404'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=50
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"An error occurred: {e}"



#====================================Testing================================


# ans = calculate_calorie_burned("football", 60)
# print(ans)



# gender                  = 'male'
# height                  = 170  # cm
# current_weight          = 100  # kg
# age                     = 25  # years
# workouts_per_week       = "Heavy"  # Updated activity level
# goal                    = 'Maintain'
# desired_weight          = 110
# diet_type               = "Lack of meal ideas"  # Default selection
# obstacle                = "Inconsistent routine"  # Default selection
# speed                   = "Fast"  # Speed to reach target: "Slow", "Normal", or "Fast"

# ans                     = develop_plan(gender, height, current_weight, age, workouts_per_week, goal, desired_weight, diet_type, obstacle, speed)

# print(ans)







# ====================================================================


import google.generativeai as genai
import json
 
# Configure the API key
API_KEY = "AIzaSyBdDZPK-Kv7phn-BZuxVzdLEI-80Wq2Fyw"  
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
 
# Function to clean and parse the response
def clean_response(response_text):
    try:
        # Replace single quotes with double quotes to make it valid JSON
        cleaned_text = response_text.strip('```python\n').strip('```')
        cleaned_text = cleaned_text.replace("'", '"')
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        return {"error": "Response could not be parsed as JSON", "text": response_text}


import json5

# Function to analyze the supplement image
def analyze_supplement_image(image_path):
    print(image_path)
    img = Image.open(image_path)
    prompt = f"""
        You are a nutrition assistant. Analyze the supplement image ({img}) and provide detailed nutritional information.
        Your tasks:
        1. Define a proper name of the supplement
        2. Try to Determine the nutritional values of the supplement based on the image. 


        Output Format:
        {{
        "name_of_supplement": "<value>"
        "carbohydrate": "<value>, "
        "protein": "<value>, "
        "calories": "<value>, "
        "macrominerals": {{"
        "P": "<value>, "
        "Mg": "<value>, "
        "Na": "<value>, "
        "K": "<value>, "
        "Ca": "<value>, "
        "Cl": "<value>, "
        "S": "<value>}}, "
        "microminerals": {{
        "Fe": "<value>, "
        "Zn": "<value>, "
        "Cu": "<value>, "
        "Mn": "<value>, "
        "Se": "<value>, "
        "I": "<value>, "
        "Cr": "<value>, "
        "Mo": "<value>, "
        "F": "<value>, "
        "Co": "<value>}}, 
        "vitamins": {{
        "A": "<value>, "
        "D": "<value>, "
        "E": "<value>, "
        "K": "<value>, "
        "C": "<<value>, "
        "B1": "<value>, "
        "B2": "<value>, "
        "B3": "<value>, "
        "B6": "<value>, "
        "B7": "<value>, "
        "B9": "<value>, "
        "B12":"<value>}}"
        }}



        "Provide values in appropriate units (e.g., milligrams or micrograms for minerals, vitamins, etc.). "
        "If specific values are not clear, provide an estimated range based on typical supplement profiles. "
        "Ensure the output is a valid Python dict."
        MAKE SURE, IF YOU DON'T FIND VALUE FOR A FIELD, RETURN EMPTY STRING FOR THAT FIELD
        "NOTE-" "RETURN ME ONLY THE DICT, NOTHING EXTRA"

    """
    
    # Generate response using the model
    response = model.generate_content([prompt, img])
    response = response.text.replace("python", '').replace("`", "").replace("'", '"')
    response = json.loads(response)

    print(response)
   
    # Clean and parse the response
    # json_output = clean_response(response.text)
 
    return response
 
# Example usage of the function
# result = analyze_supplement_image('/content/71f+UBXh2vL.AC_SX500.jpg')  
# print(result)
