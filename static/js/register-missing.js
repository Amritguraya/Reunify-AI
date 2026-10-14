/* =========================================================
   ELEMENTS
   ========================================================= */

const form =
    document.getElementById("missingChildForm");

const nameInput =
    document.getElementById("childName");

const ageInput =
    document.getElementById("age");

const genderInput =
    document.getElementById("gender");

const cityInput =
    document.getElementById("city");

const parentInput =
    document.getElementById("parentName");

const phoneInput =
    document.getElementById("phone");

const dayInput =
    document.getElementById("day");

const monthInput =
    document.getElementById("month");

const yearInput =
    document.getElementById("year");

const photoInput =
    document.getElementById("missingPhoto");

const photoPreview =
    document.getElementById("photoPreview");

const formErrors =
    document.getElementById("formErrors");

const errorList =
    document.getElementById("errorList");


/* =========================================================
   VALIDATION HELPERS
   ========================================================= */

/*
   Allows:
   Letters
   Spaces
   Hyphens
   Apostrophes
   Periods

   Examples:
   Aman Singh
   Amandeep Kaur
   Mary-Jane
   O'Connor
*/

function validPersonName(value) {

    const pattern =
        /^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '\-.][A-Za-zÀ-ÖØ-öø-ÿ]+)*$/;

    return pattern.test(value.trim());
}


/*
   City names can contain spaces, hyphens,
   apostrophes and periods.
*/

function validCity(value) {

    const pattern =
        /^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '\-.][A-Za-zÀ-ÖØ-öø-ÿ]+)*$/;

    return pattern.test(value.trim());
}


/*
   Phone = digits only
*/

function validPhone(value) {

    return /^\d{7,15}$/.test(value.trim());
}


/*
   Show field error
*/

function showError(input, errorElement, message) {

    input.classList.remove("valid");

    input.classList.add("invalid");

    errorElement.textContent = message;
}


/*
   Show field valid
*/

function showValid(input, errorElement) {

    input.classList.remove("invalid");

    input.classList.add("valid");

    errorElement.textContent = "";
}


/*
   Clear field state
*/

function clearState(input, errorElement) {

    input.classList.remove("invalid", "valid");

    errorElement.textContent = "";
}


/* =========================================================
   LIVE INPUT FILTERING
   ========================================================= */


/*
   Remove numbers from person names immediately.

   This means typing:

   Rahul123

   becomes:

   Rahul
*/

nameInput.addEventListener("input", function () {

    this.value =
        this.value.replace(/[0-9]/g, "");

});


parentInput.addEventListener("input", function () {

    this.value =
        this.value.replace(/[0-9]/g, "");

});


/*
   City should not contain numbers.
*/

cityInput.addEventListener("input", function () {

    this.value =
        this.value.replace(/[0-9]/g, "");

});


/*
   Phone should contain digits only.
*/

phoneInput.addEventListener("input", function () {

    this.value =
        this.value.replace(/\D/g, "");

});


/* =========================================================
   INDIVIDUAL VALIDATION
   ========================================================= */

function validateName() {

    const value =
        nameInput.value.trim();

    if (!value) {

        showError(
            nameInput,
            document.getElementById("nameError"),
            "Child name is required."
        );

        return false;
    }

    if (!validPersonName(value)) {

        showError(
            nameInput,
            document.getElementById("nameError"),
            "Name can contain letters, spaces, hyphens, apostrophes or periods only."
        );

        return false;
    }

    showValid(
        nameInput,
        document.getElementById("nameError")
    );

    return true;
}


function validateAge() {

    const value =
        ageInput.value.trim();

    const age =
        Number(value);

    if (!value) {

        showError(
            ageInput,
            document.getElementById("ageError"),
            "Age is required."
        );

        return false;
    }

    if (
        !Number.isInteger(age) ||
        age < 0 ||
        age > 18
    ) {

        showError(
            ageInput,
            document.getElementById("ageError"),
            "Age must be a whole number between 0 and 18."
        );

        return false;
    }

    showValid(
        ageInput,
        document.getElementById("ageError")
    );

    return true;
}


function validateGender() {

    if (!genderInput.value) {

        showError(
            genderInput,
            document.getElementById("genderError"),
            "Please select a gender."
        );

        return false;
    }

    showValid(
        genderInput,
        document.getElementById("genderError")
    );

    return true;
}


function validateCity() {

    const value =
        cityInput.value.trim();

    if (!value) {

        showError(
            cityInput,
            document.getElementById("cityError"),
            "City is required."
        );

        return false;
    }

    if (!validCity(value)) {

        showError(
            cityInput,
            document.getElementById("cityError"),
            "City cannot contain numbers or special characters."
        );

        return false;
    }

    showValid(
        cityInput,
        document.getElementById("cityError")
    );

    return true;
}


function validateParent() {

    const value =
        parentInput.value.trim();

    if (!value) {

        showError(
            parentInput,
            document.getElementById("parentError"),
            "Parent / guardian name is required."
        );

        return false;
    }

    if (!validPersonName(value)) {

        showError(
            parentInput,
            document.getElementById("parentError"),
            "Parent name cannot contain numbers."
        );

        return false;
    }

    showValid(
        parentInput,
        document.getElementById("parentError")
    );

    return true;
}


function validatePhone() {

    const value =
        phoneInput.value.trim();

    if (!value) {

        showError(
            phoneInput,
            document.getElementById("phoneError"),
            "Contact number is required."
        );

        return false;
    }

    if (!validPhone(value)) {

        showError(
            phoneInput,
            document.getElementById("phoneError"),
            "Enter a valid phone number containing 7–15 digits."
        );

        return false;
    }

    showValid(
        phoneInput,
        document.getElementById("phoneError")
    );

    return true;
}


function validatePhoto() {

    const file =
        photoInput.files[0];

    const error =
        document.getElementById("photoError");

    if (!file) {

        showError(
            photoInput,
            error,
            "Please upload a child photograph."
        );

        return false;
    }


    const allowedTypes = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ];


    if (!allowedTypes.includes(file.type)) {

        showError(
            photoInput,
            error,
            "Only JPG, PNG or WEBP images are allowed."
        );

        return false;
    }


    /*
       Keep the file below 7 MB so the complete multipart request stays
       within the server's 8 MB request limit.
    */

    if (file.size > 7 * 1024 * 1024) {

        showError(
            photoInput,
            error,
            "Photo must be smaller than 7 MB."
        );

        return false;
    }


    showValid(
        photoInput,
        error
    );

    return true;
}


function validateDate() {

    const day =
        Number(dayInput.value);

    const month =
        Number(monthInput.value);

    const year =
        Number(yearInput.value);


    const error =
        document.getElementById("dateError");


    if (!dayInput.value ||
        !monthInput.value ||
        !yearInput.value) {

        error.textContent =
            "Complete the missing date.";

        return false;
    }


    if (
        !Number.isInteger(year) ||
        year < 1900 ||
        year > 2100
    ) {

        error.textContent =
            "Enter a valid year.";

        return false;
    }


    /*
       This automatically catches:
       31 February
       31 April
       31 June
       etc.
    */

    const date =
        new Date(
            year,
            month - 1,
            day
        );


    const valid =
        date.getFullYear() === year &&
        date.getMonth() === month - 1 &&
        date.getDate() === day;


    if (!valid) {

        error.textContent =
            "The selected date is not valid.";

        return false;
    }


    error.textContent = "";

    return true;
}


/* =========================================================
   LIVE VALIDATION
   ========================================================= */

nameInput.addEventListener(
    "blur",
    validateName
);

ageInput.addEventListener(
    "blur",
    validateAge
);

genderInput.addEventListener(
    "change",
    validateGender
);

cityInput.addEventListener(
    "blur",
    validateCity
);

parentInput.addEventListener(
    "blur",
    validateParent
);

phoneInput.addEventListener(
    "blur",
    validatePhone
);

photoInput.addEventListener(
    "change",
    validatePhoto
);

dayInput.addEventListener(
    "change",
    validateDate
);

monthInput.addEventListener(
    "change",
    validateDate
);

yearInput.addEventListener(
    "blur",
    validateDate
);


/* =========================================================
   PHOTO PREVIEW
   ========================================================= */

photoInput.addEventListener(
    "change",
    function () {

        const file =
            this.files[0];

        if (!file) {

            photoPreview.innerHTML = `
                <i class="bi bi-image"></i>
                <span>Photo preview will appear here</span>
            `;

            return;
        }


        const image =
            document.createElement("img");

        image.src =
            URL.createObjectURL(file);

        image.alt =
            "Selected child photograph";


        photoPreview.innerHTML = "";

        photoPreview.appendChild(image);

    }
);


/* =========================================================
   FINAL FORM VALIDATION
   ========================================================= */

form.addEventListener(
    "submit",
    function (event) {

        const validName =
            validateName();

        const validAge =
            validateAge();

        const validGender =
            validateGender();

        const validCity =
            validateCity();

        const validParent =
            validateParent();

        const validPhone =
            validatePhone();

        const validPhoto =
            validatePhoto();

        const validDate =
            validateDate();


        const allValid =
            validName &&
            validAge &&
            validGender &&
            validCity &&
            validParent &&
            validPhone &&
            validPhoto &&
            validDate;


        if (!allValid) {

            event.preventDefault();


            /*
               Scroll to top where errors are visible.
            */

            formErrors.style.display =
                "block";


            errorList.innerHTML = "";


            const errors = [];


            if (!validName)
                errors.push("Enter a valid child name.");

            if (!validAge)
                errors.push("Enter a valid age.");

            if (!validGender)
                errors.push("Select the child's gender.");

            if (!validCity)
                errors.push("Enter a valid city.");

            if (!validParent)
                errors.push("Enter a valid parent / guardian name.");

            if (!validPhone)
                errors.push("Enter a valid contact number.");

            if (!validPhoto)
                errors.push("Upload a valid photograph.");

            if (!validDate)
                errors.push("Enter a valid missing date.");


            errors.forEach(function (message) {

                const li =
                    document.createElement("li");

                li.textContent =
                    message;

                errorList.appendChild(li);

            });


            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });

            return;
        }


        /*
           Prevent accidental double submission.
        */

        const button =
            document.getElementById("submitButton");

        button.disabled = true;

        button.innerHTML = `
            <span
                class="spinner-border spinner-border-sm"
                aria-hidden="true"
            ></span>

            Registering Case...
        `;

    }
);
