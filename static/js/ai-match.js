document.addEventListener(
    "DOMContentLoaded",
    function () {

        /* CONFIDENCE BARS */

        const bars =
            document.querySelectorAll(
                ".confidence-fill"
            );


        bars.forEach(function (bar) {

            let confidence =
                parseFloat(
                    bar.dataset.confidence || "0"
                );


            if (isNaN(confidence)) {
                confidence = 0;
            }


            confidence =
                Math.max(
                    0,
                    Math.min(
                        100,
                        confidence
                    )
                );


            setTimeout(function () {

                bar.style.width =
                    confidence + "%";

            }, 100);

        });


        /* RUN BUTTON */

        const form =
            document.getElementById("matchForm");

        const button =
            document.getElementById("runButton");


        if (form && button) {

            form.addEventListener(
                "submit",
                function () {

                    button.disabled = true;

                    button.innerHTML = `
                        <span
                            class="spinner-border spinner-border-sm"
                            aria-hidden="true">
                        </span>

                        Running AI Matching...
                    `;

                }
            );

        }

    }
);
