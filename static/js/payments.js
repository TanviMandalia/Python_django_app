function initiateRazorpayPayment(amount, appointmentId, razorpayKeyId) {
  fetch("/payments/razorpay-create-order/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify({
      amount: amount,
      appointment_id: appointmentId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === "success") {
        const options = {
          key: data.key_id || razorpayKeyId,
          amount: data.amount,
          currency: data.currency,
          name: "PhysioRehab Clinic",
          description: "Consultation & Treatment Payment",
          order_id: data.order_id,
          handler: function (response) {
            verifyPayment(response);
          },
          theme: {
            color: "#F5C518",
          },
        };
        const rzp = new Razorpay(options);
        rzp.open();
      } else {
        Swal.fire({
          icon: "error",
          title: "Order Failed",
          text: data.message || "Could not initialize payment.",
        });
      }
    })
    .catch((err) => {
      console.error(err);
      Swal.fire({
        icon: "error",
        title: "Connection Error",
        text: "Please check your network and try again.",
      });
    });
}

function verifyPayment(paymentResponse) {
  fetch("/payments/razorpay-verify/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify(paymentResponse),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "success") {
        Swal.fire({
          icon: "success",
          title: "Payment Successful!",
          text: "Your payment has been verified and confirmed.",
        }).then(() => {
          window.location.reload();
        });
      } else {
        Swal.fire({
          icon: "error",
          title: "Verification Failed",
          text: data.message,
        });
      }
    });
}

function getCsrfToken() {
  const cookieValue = document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="))
    ?.split("=")[1];
  return cookieValue || "";
}

