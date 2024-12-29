document.getElementById ('appointment-form') . addEventListener ('submit', function (event) {
    const name = document.getElementById ('name') . value;
    const date = document.getElementById ('date') .value;
    const time = document.getElementById ('time') .value;


    
    
    if (!name || !date || !time) {
    alert ('Veuillez remplir tous les champs. ') ;
    event.preventDefault ();}
});

