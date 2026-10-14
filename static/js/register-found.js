document.addEventListener("DOMContentLoaded", function () {

    const form =
        document.getElementById("foundChildForm");

    const age =
        document.getElementById("estimatedAge");

    const reporterName =
        document.getElementById("reporterName");

    const reporterContact =
        document.getElementById("reporterContact");

    const locationFound =
        document.getElementById("locationFound");

    const year =
        document.getElementById("year");

    const description =
        document.getElementById("description");

    const photo =
        document.getElementById("foundPhoto");

    const photoPreview =
        document.getElementById("foundPhotoPreview");

    const photoError =
        document.getElementById("photoError");

    const descriptionCount =
        document.getElementById("descriptionCount");


    /* =====================================================
       REPORTER NAME
       Letters + spaces + hyphen + apostrophe
    ===================================================== */

    reporterName.addEventListener("input", function () {

        this.value =
            this.value.replace(
                /[^A-Za-zÀ-ÖØ-öø-ÿ' -]/g,
                ""
            );

    });


    /* =====================================================
       CONTACT NUMBER
       DIGITS ONLY
    ===================================================== */

    reporterContact.addEventListener("input", function () {

        this.value =
            this.value.replace(
                /[^0-9]/g,
                ""
            );

        if (this.value.length > 15) {

            this.value =
                this.value.substring(0, 15);

        }

    });


    /* =====================================================
       AGE
    ===================================================== */

    age.addEventListener("input", function () {

        let value =
            parseInt(this.value);

        if (isNaN(value)) {
            return;
        }

        if (value < 0) {
            this.value = 0;
        }

        if (value > 18) {
            this.value = 18;
        }

    });


    /* =====================================================
       YEAR
    ===================================================== */

    year.addEventListener("input", function () {

        let value =
            parseInt(this.value);

        if (isNaN(value)) {
            return;
        }

        if (value > 2100) {
            this.value = 2100;
        }

        if (value < 0) {
            this.value = "";
        }

    });


    /* =====================================================
       LOCATION
    ===================================================== */

    locationFound.addEventListener("input", function () {

        this.value =
            this.value.replace(
                /[^A-Za-zÀ-ÖØ-öø-ÿ0-9'.,()\/& -]/g,
                ""
            );

    });


    /* =====================================================
       DESCRIPTION COUNTER
    ===================================================== */

    description.addEventListener("input", function () {

        descriptionCount.textContent =
            this.value.length;

    });


    /* =====================================================
       PHOTO PREVIEW + VALIDATION
    ===================================================== */

    photo.addEventListener("change", function () {

        photoError.textContent = "";

        photo.classList.remove("is-invalid");
        photo.classList.remove("is-valid");


        const file =
            this.files[0];


        if (!file) {

            photoPreview.innerHTML = `
                <i class="bi bi-image"></i>
                <span>Photo preview will appear here</span>
            `;

            return;

        }


        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];


        if (!allowedTypes.includes(file.type)) {

            photo.value = "";

            photoPreview.innerHTML = `
                <i class="bi bi-image"></i>
                <span>Photo preview will appear here</span>
            `;

            photo.classList.add("is-invalid");

            photoError.textContent =
                "Only JPG, PNG and WEBP images are allowed.";

            return;

        }


        /* Leave room for multipart fields under the server's 8 MB limit. */

        if (file.size > 7 * 1024 * 1024) {

            photo.value = "";

            photoPreview.innerHTML = `
                <i class="bi bi-image"></i>
                <span>Photo preview will appear here</span>
            `;

            photo.classList.add("is-invalid");

            photoError.textContent =
                "Photo must be smaller than 7 MB.";

            return;

        }


        const image =
            document.createElement("img");


        image.src =
            URL.createObjectURL(file);


        image.alt =
            "Selected found child photograph";


        image.onload = function () {

            URL.revokeObjectURL(
                image.src
            );

        };


        photoPreview.innerHTML = "";

        photoPreview.appendChild(image);

        photo.classList.add("is-valid");

    });


    /* =====================================================
       FORM VALIDATION
    ===================================================== */

    form.addEventListener("submit", function (event) {

        let valid = true;


        /* AGE */

        const ageValue =
            parseInt(age.value);

        if (
            isNaN(ageValue) ||
            ageValue < 0 ||
            ageValue > 18
        ) {

            age.classList.add("is-invalid");

            valid = false;

        } else {

            age.classList.remove("is-invalid");
            age.classList.add("is-valid");

        }


        /* REPORTER NAME */

        const nameValue =
            reporterName.value.trim();


        const namePattern =
            /^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$/;


        if (
            nameValue.length < 2 ||
            !namePattern.test(nameValue)
        ) {

            reporterName.classList.add("is-invalid");

            valid = false;

        } else {

            reporterName.classList.remove("is-invalid");
            reporterName.classList.add("is-valid");

        }


        /* CONTACT */

        const contactValue =
            reporterContact.value.trim();


        if (
            !/^[0-9]{7,15}$/.test(contactValue)
        ) {

            reporterContact.classList.add("is-invalid");

            valid = false;

        } else {

            reporterContact.classList.remove("is-invalid");
            reporterContact.classList.add("is-valid");

        }


        /* LOCATION */

        if (
            locationFound.value.trim().length < 2
        ) {

            locationFound.classList.add("is-invalid");

            valid = false;

        } else {

            locationFound.classList.remove("is-invalid");
            locationFound.classList.add("is-valid");

        }


        /* YEAR */

        const yearValue =
            parseInt(year.value);


        if (
            isNaN(yearValue) ||
            yearValue < 1900 ||
            yearValue > 2100
        ) {

            year.classList.add("is-invalid");

            valid = false;

        } else {

            year.classList.remove("is-invalid");
            year.classList.add("is-valid");

        }


        /* PHOTO */

        if (!photo.files.length) {

            photo.classList.add("is-invalid");

            photoError.textContent =
                "Please select a photograph.";

            valid = false;

        }


        /* STOP SUBMISSION */

        if (!valid) {

            event.preventDefault();

            const firstInvalid =
                form.querySelector(
                    ".is-invalid"
                );

            if (firstInvalid) {

                firstInvalid.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

                firstInvalid.focus();

            }

            return;

        }

    });


    /* =====================================================
       REMOVE INVALID STATE WHILE USER FIXES INPUT
    ===================================================== */

    [
        age,
        reporterName,
        reporterContact,
        locationFound,
        year
    ].forEach(function (field) {

        field.addEventListener(
            "input",
            function () {

                if (this.value.trim() !== "") {

                    this.classList.remove(
                        "is-invalid"
                    );

                }

            }
        );

    });


});
