/*const textBtn = document.getElementById('text2');
textBtn.addEventListener('click', (event) => {
 event.preventDefault();
 alert(2);
});*/

  async function getText(){  
const res = await fetch("/article/"+id);
const result = await res.text();
  
return result;
} 

$(document).on('click', '.btn-info', function (event) {
  //event.preventDefault();
  var url = $(this).parent().find(".url")[0].href;
  /*fetch("/article/"+id).then((respone)=>{
    respone.text().then((data)=>{
      console.log(data);
      //alert(data)
      $(this).siblings().find(".code")[0].innerHTML = data
      })
   })
*/
$("#precode")[0].src=url;
console.log($("#precode"))
});

