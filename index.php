<?php
  /*

   __      __      ___.        .___             __
  /  \    /  \ ____\_ |__    __| _/____   ____ |  | __
  \   \/\/   // __ \| __ \  / __ |/  _ \_/ ___\|  |/ /
   \        /\  ___/| \_\ \/ /_/ (  <_> )  \___|    <
    \__/\  /  \___  >___  /\____ |\____/ \___  >__|_ \
         \/       \/    \/      \/           \/     \/

     Webdock Welcome Page - YOU SHOULD DELETE THIS FILE

  */

  //User wants to show phpinfo
  if (array_key_exists("phpinfo",$_REQUEST)) {
      phpinfo();
      exit();
  }

?><!doctype html>
<html lang="en">
  <head>

    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

    <title>Welcome to your new Webdock server!</title>
  </head>
  <body class="background-video-wrapper">
    <div class="overlay"></div>
    <div class="wrapper">
      <div class="scrollable">
         <div class="container">
           <div class="text-center">

        <p><img class="img-fluid" src="https://webdock.io/application/themes/webdock/img/webdock-logo-positiv-newtagline.svg"></p>

        <h1>Welcome to your new Webdock server.</h1>

        <div class="animateIn" style="--animation-order: 1;">

          <p>This is the index.php file in your web root which is located at /var/www/html.<br>You should delete this file.</p>

          <hr>
        </div>

        <div class="animateIn" style="--animation-order: 2;">
          <h2>FTP is enabled on this server</h2>
          <p>You should be aware that FTP is enabled and active on this server. Fail2Ban is enabled and will ban IPs after 5 failed login attempts. If you do not intend to use FTP, or feel this is a security risk you should run the &quot;Disable FTP&quot; script on this server (find it in the script library)</p>

          <hr>
        </div>

        <div class="animateIn" style="--animation-order: 3;">
          <h2>Sudo commands require a password</h2>
          <p>Webdock servers are configured such that you need to enter a password when executing sudo commands. If you want to change this behavior, please enable &quot;Passwordless Sudo&quot; on the Shell Users screen for this server. </p>

          <hr>
        </div>

        <div class="animateIn" style="--animation-order: 4;">
          <h2>MongoDB is installed but disabled</h2>
          <p>If you want to use MongoDB on this server, please run the "Enable MongoDB" script on this server (find it on the Scripts page)</p>
          <hr>
        </div>

        <div class="animateIn" style="--animation-order: 5;">
          <h2>Here's some stuff you might need</h2>

          <p>
            <a class="btn" href="/index.php?phpinfo" role="button">phpinfo()</a> <a class="btn" href="/phpmyadmin" role="button">phpMyAdmin</a> <a class="btn" href="https://webdock.io/en/docs/stacks" role="button">Stacks docs</a>
          </p>
        </div>

       </div>
        </div>
    </div>

    </div>
    <div id="particles-js"></div>
<style>
@import url('https://fonts.googleapis.com/css?family=Raleway:400,700');
* {
  -webkit-box-sizing: border-box;
          box-sizing: border-box;
  margin: 0;
  padding: 0;
  font-weight: 300;
}
html,body {
  height: 100%;
}
body {
  font-family: 'Raleway', sans-serif;
  color: #000;
  font-weight: 300;

}
.img-fluid {
  max-width: 100%;
  width: 37%;
}
p {
  margin-top: 20px;
  margin-bottom: 20px;
}
hr {
  overflow: visible; /* For IE */
  padding: 0;
  margin-top: 25px;
  border: none;
  border-top: thin solid #3fb87f;
  color: #00a1a1;
  text-align: center;
}
hr:after {
  content: '\0026A1';
  display: inline-block;
  position: relative;
  top: -0.7em;
  font-size: 1.5em;
  padding: 0 0.25em;
  background: white;
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #018647;
  background: -moz-linear-gradient(left, #018647 0%, #008570 50%, #008685 100%);
  background: -webkit-linear-gradient(left, #018647 0%, #008570 50%, #008685 100%);
  background: linear-gradient(to right, #018647 0%, #008570 50%, #008685 100%);
  filter: progid:DXImageTransform.Microsoft.gradient(startColorstr='#018647', endColorstr='#008685', GradientType=1);

  opacity: 0.8;
}
.wrapper {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.scrollable {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  position: relative;
  z-index: 2;
}
.container {
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
  margin-top: 40px;
  margin-bottom: 40px;
  padding-left: 40px;
  padding-right: 40px;
  padding-top: 20px;
  padding-bottom: 20px;
  background-color: #fff;
  box-shadow: 0 3px 3px 0 rgba(0,0,0,0.14), 0 1px 7px 0 rgba(0,0,0,0.12), 0 3px 1px -1px rgba(0,0,0,0.2);
  border-radius: 4px;
  position: relative;
  z-index: 2;
}
.text-center {
  text-align: center;
}
.btn {
  text-decoration: none;
  color: #fff;
  background-color: #00a1a1;
  text-align: center;
  letter-spacing: .5px;
  transition: .2s ease-out;
  cursor: pointer;
  border: none;
  border-radius: 2px;
  display: inline-block;
  height: 36px;
  width: 170px;
  margin: 5px;
  line-height: 36px;
  padding: 0 2rem;
  vertical-align: middle;
  -webkit-tap-highlight-color: transparent;
  -webkit-box-shadow: 0 3px 7px rgba(0, 0, 0, 0.3);
  -moz-box-shadow: 0 3px 7px rgba(0, 0, 0, 0.3);
  box-shadow: 0 3px 7px rgba(0, 0, 0, 0.3);
  background: #ffffff;
  background: -moz-linear-gradient(left, #ffffff 0%, #ffffff 50%, #ffffff 100%);
  background: -webkit-linear-gradient(left, #ffffff 0%, #ffffff 50%, #ffffff 100%);
  background: linear-gradient(to right, #ffffff 0%, #ffffff 50%, #ffffff 100%);
  filter: progid:DXImageTransform.Microsoft.gradient(startColorstr='#ffffff', endColorstr='#ffffff', GradientType=1);
  color: #47ad5a;
}
.btn:hover {
box-shadow: 0 3px 3px 0 rgba(0,0,0,0.14), 0 1px 7px 0 rgba(0,0,0,0.12), 0 3px 1px -1px rgba(0,0,0,0.2);
}

.animateIn {
  display: block;
  animation-name: animateIn;
  animation-duration: 350ms;
  animation-delay: calc(var(--animation-order) * 250ms);
  animation-fill-mode: both;
  animation-timing-function: ease-in-out;
}
@keyframes animateIn {
  0% {
    opacity: 0;
    transform: scale(0.6) translateY(-8px);
  }

  100% {
    opacity: 1;
  }
}

/* Respond */
@media (max-width: 600px) {
  .img-fluid {
    width: 100%;
  }
  .container {
    padding: 20px;
    margin-top: 0px;
    margin-bottom: 0px;
  }
}


#particles-js canvas {
        width: 100%;
        max-width: 100%;
        position: absolute;
        overflow: hidden;
        top: 0;
        /*z-index: 2; */
        max-height: 100vh;
}

/* Vidbg */
.vidbg-container{position:absolute;z-index:-1;top:0;right:0;bottom:0;left:0;overflow:hidden;background-size:cover;background-repeat:no-repeat;background-position:center center}.vidbg-container video{position:absolute;margin:0;top:50%;left:50%;transform:translate(-50%, -50%);transition:0.25s opacity ease-in-out;max-width:none;opacity:0}.vidbg-overlay{position:absolute;top:0;right:0;bottom:0;left:0}

</style>
<script>
  /*!
   * vidbg.js v2.0.1 (https://github.com/blakewilson/vidbg)
   * vidbg.js By Blake Wilson
   * @license Licensed Under MIT (https://github.com/blakewilson/vidbg/blob/master/LICENSE)
   */
  var vidbg=function(e){var t={};function r(n){if(t[n])return t[n].exports;var o=t[n]={i:n,l:!1,exports:{}};return e[n].call(o.exports,o,o.exports,r),o.l=!0,o.exports}return r.m=e,r.c=t,r.d=function(e,t,n){r.o(e,t)||Object.defineProperty(e,t,{enumerable:!0,get:n})},r.r=function(e){"undefined"!=typeof Symbol&&Symbol.toStringTag&&Object.defineProperty(e,Symbol.toStringTag,{value:"Module"}),Object.defineProperty(e,"__esModule",{value:!0})},r.t=function(e,t){if(1&t&&(e=r(e)),8&t)return e;if(4&t&&"object"==typeof e&&e&&e.__esModule)return e;var n=Object.create(null);if(r.r(n),Object.defineProperty(n,"default",{enumerable:!0,value:e}),2&t&&"string"!=typeof e)for(var o in e)r.d(n,o,function(t){return e[t]}.bind(null,o));return n},r.n=function(e){var t=e&&e.__esModule?function(){return e.default}:function(){return e};return r.d(t,"a",t),t},r.o=function(e,t){return Object.prototype.hasOwnProperty.call(e,t)},r.p="",r(r.s=1)}([function(e,t,r){"use strict";var n="#?[".concat("a-f\\d","]{3}[").concat("a-f\\d","]?"),o="#?[".concat("a-f\\d","]{6}([").concat("a-f\\d","]{2})?"),i=new RegExp("[^#".concat("a-f\\d","]"),"gi"),a=new RegExp("^".concat(n,"$|^").concat(o,"$"),"i");e.exports=function(e){var t=arguments.length>1&&void 0!==arguments[1]?arguments[1]:{};if("string"!=typeof e||i.test(e)||!a.test(e))throw new TypeError("Expected a valid hex string");var r=1;8===(e=e.replace(/^#/,"")).length&&(r=parseInt(e.slice(6,8),16)/255,e=e.slice(0,6)),4===e.length&&(r=parseInt(e.slice(3,4).repeat(2),16)/255,e=e.slice(0,3)),3===e.length&&(e=e[0]+e[0]+e[1]+e[1]+e[2]+e[2]);var n=parseInt(e,16),o=n>>16,l=n>>8&255,c=255&n;return"array"===t.format?[o,l,c,r]:{red:o,green:l,blue:c,alpha:r}}},function(e,t,r){"use strict";r.r(t);var n=r(0),o=r.n(n);function i(e){for(var t=1;t<arguments.length;t++){var r=null!=arguments[t]?arguments[t]:{},n=Object.keys(r);"function"==typeof Object.getOwnPropertySymbols&&(n=n.concat(Object.getOwnPropertySymbols(r).filter((function(e){return Object.getOwnPropertyDescriptor(r,e).enumerable})))),n.forEach((function(t){c(e,t,r[t])}))}return e}function a(e,t){return function(e){if(Array.isArray(e))return e}(e)||function(e,t){var r=[],n=!0,o=!1,i=void 0;try{for(var a,l=e[Symbol.iterator]();!(n=(a=l.next()).done)&&(r.push(a.value),!t||r.length!==t);n=!0);}catch(e){o=!0,i=e}finally{try{n||null==l.return||l.return()}finally{if(o)throw i}}return r}(e,t)||function(){throw new TypeError("Invalid attempt to destructure non-iterable instance")}()}function l(e,t){for(var r=0;r<t.length;r++){var n=t[r];n.enumerable=n.enumerable||!1,n.configurable=!0,"value"in n&&(n.writable=!0),Object.defineProperty(e,n.key,n)}}function c(e,t,r){return t in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}
  var s=function(){function e(t,r,n){var l=this;if(function(e,t){if(!(e instanceof t))throw new TypeError("Cannot call a class as a function")}(this,e),c(this,"createContainer",(function(){l.containerEl=document.createElement("div"),l.containerEl.className="vidbg-container",l.createPoster(),l.el.appendChild(l.containerEl)})),c(this,"createOverlay",(function(){if(l.overlayEl=document.createElement("div"),l.overlayEl.className="vidbg-overlay",l.options.overlay){var e=a(o()(l.options.overlayColor,{format:"array"}),3),t=[e[0],e[1],e[2],l.options.overlayAlpha];l.overlayEl.style.backgroundColor="rgba(".concat(t.join(", "),")")}l.containerEl.appendChild(l.overlayEl)})),c(this,"createPoster",(function(){l.options.poster&&(l.containerEl.style.backgroundImage="url(".concat(l.options.poster,")"))})),c(this,"createVideo",(function(){for(var e in l.videoEl=document.createElement("video"),l.videoEl.addEventListener("playing",l.onPlayEvent),l.attributes)l.videoEl[e]=l.attributes[e];if(l.options.mp4){var t=document.createElement("source");t.src=l.options.mp4,t.type="video/mp4",l.videoEl.appendChild(t)}if(l.options.webm){var r=document.createElement("source");r.src=l.options.webm,r.type="video/webm",l.videoEl.appendChild(r)}l.containerEl.appendChild(l.videoEl);var n=l.videoEl.play();void 0!==n&&n.catch((function(e){console.error(e),console.error("Autoplay is not supported"),l.removeVideo()}))})),c(this,"onPlayEvent",(function(e){l.resize(),l.videoEl.style.opacity=1})),c(this,"removeVideo",(function(){l.videoEl.remove()})),c(this,"getVideo",(function(){return l.videoEl})),c(this,"destroy",(function(){l.containerEl.remove()})),c(this,"resize",(function(){var e=l.containerEl.offsetWidth,t=l.containerEl.offsetHeight;e/l.videoEl.videoWidth>t/l.videoEl.videoHeight?(l.videoEl.style.width="".concat(e,"px"),l.videoEl.style.height="auto"):(l.videoEl.style.width="auto",l.videoEl.style.height="".concat(t,"px"))})),!t)return console.error("Please provide a selector"),!1;if(this.el=document.querySelector(t),!this.el)return console.error('The selector you specified, "'.concat(t,'", does not exist!')),!1;this.options=i({},{mp4:null,webm:null,poster:null,overlay:!1,overlayColor:"#000",overlayAlpha:.3},r);if(this.attributes=i({},{controls:!1,loop:!0,muted:!0,playsInline:!0},n),!this.options.mp4&&!this.options.webm)return console.error("Please provide an mp4, webm, or both."),!1;this.init()}var t,r,n;return t=e,(r=[{key:"init",value:function(){this.el.style.position="relative",this.el.style.zIndex=1,this.createContainer(),this.createVideo(),this.createOverlay(),window.addEventListener("resize",this.resize)}}])&&l(t.prototype,r),n&&l(t,n),e}();t.default=s}]).default;
/* -----------------------------------------------
/* Author : Vincent Garreau  - vincentgarreau.com
/* MIT license: http://opensource.org/licenses/MIT
/* Demo / Generator : vincentgarreau.com/particles.js
/* GitHub : github.com/VincentGarreau/particles.js
/* How to use? : Check the GitHub README
/* v2.0.0
/* ----------------------------------------------- */
var pJS=function(e,a){var t=document.querySelector("#"+e+" > .particles-js-canvas-el");this.pJS={canvas:{el:t,w:t.offsetWidth,h:t.offsetHeight},particles:{number:{value:400,density:{enable:!0,value_area:800}},color:{value:"#fff"},shape:{type:"circle",stroke:{width:0,color:"#ff0000"},polygon:{nb_sides:5},image:{src:"",width:100,height:100}},opacity:{value:1,random:!1,anim:{enable:!1,speed:2,opacity_min:0,sync:!1}},size:{value:20,random:!1,anim:{enable:!1,speed:20,size_min:0,sync:!1}},line_linked:{enable:!0,distance:100,color:"#fff",opacity:1,width:1},move:{enable:!0,speed:2,direction:"none",random:!1,straight:!1,out_mode:"out",bounce:!1,attract:{enable:!1,rotateX:3e3,rotateY:3e3}},array:[]},interactivity:{detect_on:"canvas",events:{onhover:{enable:!0,mode:"grab"},onclick:{enable:!0,mode:"push"},resize:!0},modes:{grab:{distance:100,line_linked:{opacity:1}},bubble:{distance:200,size:80,duration:.4},repulse:{distance:200,duration:.4},push:{particles_nb:4},remove:{particles_nb:2}},mouse:{}},retina_detect:!1,fn:{interact:{},modes:{},vendors:{}},tmp:{}};var d=this.pJS;a&&Object.deepExtend(d,a),d.tmp.obj={size_value:d.particles.size.value,size_anim_speed:d.particles.size.anim.speed,move_speed:d.particles.move.speed,line_linked_distance:d.particles.line_linked.distance,line_linked_width:d.particles.line_linked.width,mode_grab_distance:d.interactivity.modes.grab.distance,mode_bubble_distance:d.interactivity.modes.bubble.distance,mode_bubble_size:d.interactivity.modes.bubble.size,mode_repulse_distance:d.interactivity.modes.repulse.distance},d.fn.retinaInit=function(){d.retina_detect&&1<window.devicePixelRatio?(d.canvas.pxratio=window.devicePixelRatio,d.tmp.retina=!0):(d.canvas.pxratio=1,d.tmp.retina=!1),d.canvas.w=d.canvas.el.offsetWidth*d.canvas.pxratio,d.canvas.h=d.canvas.el.offsetHeight*d.canvas.pxratio,d.particles.size.value=d.tmp.obj.size_value*d.canvas.pxratio,d.particles.size.anim.speed=d.tmp.obj.size_anim_speed*d.canvas.pxratio,d.particles.move.speed=d.tmp.obj.move_speed*d.canvas.pxratio,d.particles.line_linked.distance=d.tmp.obj.line_linked_distance*d.canvas.pxratio,d.interactivity.modes.grab.distance=d.tmp.obj.mode_grab_distance*d.canvas.pxratio,d.interactivity.modes.bubble.distance=d.tmp.obj.mode_bubble_distance*d.canvas.pxratio,d.particles.line_linked.width=d.tmp.obj.line_linked_width*d.canvas.pxratio,d.interactivity.modes.bubble.size=d.tmp.obj.mode_bubble_size*d.canvas.pxratio,d.interactivity.modes.repulse.distance=d.tmp.obj.mode_repulse_distance*d.canvas.pxratio},d.fn.canvasInit=function(){d.canvas.ctx=d.canvas.el.getContext("2d")},d.fn.canvasSize=function(){d.canvas.el.width=d.canvas.w,d.canvas.el.height=d.canvas.h,d&&d.interactivity.events.resize&&window.addEventListener("resize",function(){d.canvas.w=d.canvas.el.offsetWidth,d.canvas.h=d.canvas.el.offsetHeight,d.tmp.retina&&(d.canvas.w*=d.canvas.pxratio,d.canvas.h*=d.canvas.pxratio),d.canvas.el.width=d.canvas.w,d.canvas.el.height=d.canvas.h,d.particles.move.enable||(d.fn.particlesEmpty(),d.fn.particlesCreate(),d.fn.particlesDraw(),d.fn.vendors.densityAutoParticles()),d.fn.vendors.densityAutoParticles()})},d.fn.canvasPaint=function(){d.canvas.ctx.fillRect(0,0,d.canvas.w,d.canvas.h)},d.fn.canvasClear=function(){d.canvas.ctx.clearRect(0,0,d.canvas.w,d.canvas.h)},d.fn.particle=function(e,a,t){if(this.radius=(d.particles.size.random?Math.random():1)*d.particles.size.value,d.particles.size.anim.enable&&(this.size_status=!1,this.vs=d.particles.size.anim.speed/100,d.particles.size.anim.sync||(this.vs=this.vs*Math.random())),this.x=t?t.x:Math.random()*d.canvas.w,this.y=t?t.y:Math.random()*d.canvas.h,this.x>d.canvas.w-2*this.radius?this.x=this.x-this.radius:this.x<2*this.radius&&(this.x=this.x+this.radius),this.y>d.canvas.h-2*this.radius?this.y=this.y-this.radius:this.y<2*this.radius&&(this.y=this.y+this.radius),d.particles.move.bounce&&d.fn.vendors.checkOverlap(this,t),this.color={},"object"==typeof e.value)if(e.value instanceof Array){var i=e.value[Math.floor(Math.random()*d.particles.color.value.length)];this.color.rgb=hexToRgb(i)}else null!=e.value.r&&null!=e.value.g&&null!=e.value.b&&(this.color.rgb={r:e.value.r,g:e.value.g,b:e.value.b}),null!=e.value.h&&null!=e.value.s&&null!=e.value.l&&(this.color.hsl={h:e.value.h,s:e.value.s,l:e.value.l});else"random"==e.value?this.color.rgb={r:Math.floor(256*Math.random())+0,g:Math.floor(256*Math.random())+0,b:Math.floor(256*Math.random())+0}:"string"==typeof e.value&&(this.color=e,this.color.rgb=hexToRgb(this.color.value));this.opacity=(d.particles.opacity.random?Math.random():1)*d.particles.opacity.value,d.particles.opacity.anim.enable&&(this.opacity_status=!1,this.vo=d.particles.opacity.anim.speed/100,d.particles.opacity.anim.sync||(this.vo=this.vo*Math.random()));var s={};switch(d.particles.move.direction){case"top":s={x:0,y:-1};break;case"top-right":s={x:.5,y:-.5};break;case"right":s={x:1,y:-0};break;case"bottom-right":s={x:.5,y:.5};break;case"bottom":s={x:0,y:1};break;case"bottom-left":s={x:-.5,y:1};break;case"left":s={x:-1,y:0};break;case"top-left":s={x:-.5,y:-.5};break;default:s={x:0,y:0}}d.particles.move.straight?(this.vx=s.x,this.vy=s.y,d.particles.move.random&&(this.vx=this.vx*Math.random(),this.vy=this.vy*Math.random())):(this.vx=s.x+Math.random()-.5,this.vy=s.y+Math.random()-.5),this.vx_i=this.vx,this.vy_i=this.vy;var n=d.particles.shape.type;if("object"==typeof n){if(n instanceof Array){var r=n[Math.floor(Math.random()*n.length)];this.shape=r}}else this.shape=n;if("image"==this.shape){var c=d.particles.shape;this.img={src:c.image.src,ratio:c.image.width/c.image.height},this.img.ratio||(this.img.ratio=1),"svg"==d.tmp.img_type&&null!=d.tmp.source_svg&&(d.fn.vendors.createSvgImg(this),d.tmp.pushing&&(this.img.loaded=!1))}},d.fn.particle.prototype.draw=function(){var e=this;if(null!=e.radius_bubble)var a=e.radius_bubble;else a=e.radius;if(null!=e.opacity_bubble)var t=e.opacity_bubble;else t=e.opacity;if(e.color.rgb)var i="rgba("+e.color.rgb.r+","+e.color.rgb.g+","+e.color.rgb.b+","+t+")";else i="hsla("+e.color.hsl.h+","+e.color.hsl.s+"%,"+e.color.hsl.l+"%,"+t+")";switch(d.canvas.ctx.fillStyle=i,d.canvas.ctx.beginPath(),e.shape){case"circle":d.canvas.ctx.arc(e.x,e.y,a,0,2*Math.PI,!1);break;case"edge":d.canvas.ctx.rect(e.x-a,e.y-a,2*a,2*a);break;case"triangle":d.fn.vendors.drawShape(d.canvas.ctx,e.x-a,e.y+a/1.66,2*a,3,2);break;case"polygon":d.fn.vendors.drawShape(d.canvas.ctx,e.x-a/(d.particles.shape.polygon.nb_sides/3.5),e.y-a/.76,2.66*a/(d.particles.shape.polygon.nb_sides/3),d.particles.shape.polygon.nb_sides,1);break;case"star":d.fn.vendors.drawShape(d.canvas.ctx,e.x-2*a/(d.particles.shape.polygon.nb_sides/4),e.y-a/1.52,2*a*2.66/(d.particles.shape.polygon.nb_sides/3),d.particles.shape.polygon.nb_sides,2);break;case"image":;if("svg"==d.tmp.img_type)var s=e.img.obj;else s=d.tmp.img_obj;s&&d.canvas.ctx.drawImage(s,e.x-a,e.y-a,2*a,2*a/e.img.ratio)}d.canvas.ctx.closePath(),0<d.particles.shape.stroke.width&&(d.canvas.ctx.strokeStyle=d.particles.shape.stroke.color,d.canvas.ctx.lineWidth=d.particles.shape.stroke.width,d.canvas.ctx.stroke()),d.canvas.ctx.fill()},d.fn.particlesCreate=function(){for(var e=0;e<d.particles.number.value;e++)d.particles.array.push(new d.fn.particle(d.particles.color,d.particles.opacity.value))},d.fn.particlesUpdate=function(){for(var e=0;e<d.particles.array.length;e++){var a=d.particles.array[e];if(d.particles.move.enable){var t=d.particles.move.speed/2;a.x+=a.vx*t,a.y+=a.vy*t}if(d.particles.opacity.anim.enable&&(1==a.opacity_status?(a.opacity>=d.particles.opacity.value&&(a.opacity_status=!1),a.opacity+=a.vo):(a.opacity<=d.particles.opacity.anim.opacity_min&&(a.opacity_status=!0),a.opacity-=a.vo),a.opacity<0&&(a.opacity=0)),d.particles.size.anim.enable&&(1==a.size_status?(a.radius>=d.particles.size.value&&(a.size_status=!1),a.radius+=a.vs):(a.radius<=d.particles.size.anim.size_min&&(a.size_status=!0),a.radius-=a.vs),a.radius<0&&(a.radius=0)),"bounce"==d.particles.move.out_mode)var i={x_left:a.radius,x_right:d.canvas.w,y_top:a.radius,y_bottom:d.canvas.h};else i={x_left:-a.radius,x_right:d.canvas.w+a.radius,y_top:-a.radius,y_bottom:d.canvas.h+a.radius};switch(a.x-a.radius>d.canvas.w?(a.x=i.x_left,a.y=Math.random()*d.canvas.h):a.x+a.radius<0&&(a.x=i.x_right,a.y=Math.random()*d.canvas.h),a.y-a.radius>d.canvas.h?(a.y=i.y_top,a.x=Math.random()*d.canvas.w):a.y+a.radius<0&&(a.y=i.y_bottom,a.x=Math.random()*d.canvas.w),d.particles.move.out_mode){case"bounce":a.x+a.radius>d.canvas.w?a.vx=-a.vx:a.x-a.radius<0&&(a.vx=-a.vx),a.y+a.radius>d.canvas.h?a.vy=-a.vy:a.y-a.radius<0&&(a.vy=-a.vy)}if(isInArray("grab",d.interactivity.events.onhover.mode)&&d.fn.modes.grabParticle(a),(isInArray("bubble",d.interactivity.events.onhover.mode)||isInArray("bubble",d.interactivity.events.onclick.mode))&&d.fn.modes.bubbleParticle(a),(isInArray("repulse",d.interactivity.events.onhover.mode)||isInArray("repulse",d.interactivity.events.onclick.mode))&&d.fn.modes.repulseParticle(a),d.particles.line_linked.enable||d.particles.move.attract.enable)for(var s=e+1;s<d.particles.array.length;s++){var n=d.particles.array[s];d.particles.line_linked.enable&&d.fn.interact.linkParticles(a,n),d.particles.move.attract.enable&&d.fn.interact.attractParticles(a,n),d.particles.move.bounce&&d.fn.interact.bounceParticles(a,n)}}},d.fn.particlesDraw=function(){d.canvas.ctx.clearRect(0,0,d.canvas.w,d.canvas.h),d.fn.particlesUpdate();for(var e=0;e<d.particles.array.length;e++){d.particles.array[e].draw()}},d.fn.particlesEmpty=function(){d.particles.array=[]},d.fn.particlesRefresh=function(){cancelRequestAnimFrame(d.fn.checkAnimFrame),cancelRequestAnimFrame(d.fn.drawAnimFrame),d.tmp.source_svg=void 0,d.tmp.img_obj=void 0,d.tmp.count_svg=0,d.fn.particlesEmpty(),d.fn.canvasClear(),d.fn.vendors.start()},d.fn.interact.linkParticles=function(e,a){var t=e.x-a.x,i=e.y-a.y,s=Math.sqrt(t*t+i*i);if(s<=d.particles.line_linked.distance){var n=d.particles.line_linked.opacity-s/(1/d.particles.line_linked.opacity)/d.particles.line_linked.distance;if(0<n){var r=d.particles.line_linked.color_rgb_line;d.canvas.ctx.strokeStyle="rgba("+r.r+","+r.g+","+r.b+","+n+")",d.canvas.ctx.lineWidth=d.particles.line_linked.width,d.canvas.ctx.beginPath(),d.canvas.ctx.moveTo(e.x,e.y),d.canvas.ctx.lineTo(a.x,a.y),d.canvas.ctx.stroke(),d.canvas.ctx.closePath()}}},d.fn.interact.attractParticles=function(e,a){var t=e.x-a.x,i=e.y-a.y;if(Math.sqrt(t*t+i*i)<=d.particles.line_linked.distance){var s=t/(1e3*d.particles.move.attract.rotateX),n=i/(1e3*d.particles.move.attract.rotateY);e.vx-=s,e.vy-=n,a.vx+=s,a.vy+=n}},d.fn.interact.bounceParticles=function(e,a){var t=e.x-a.x,i=e.y-a.y;Math.sqrt(t*t+i*i)<=e.radius+a.radius&&(e.vx=-e.vx,e.vy=-e.vy,a.vx=-a.vx,a.vy=-a.vy)},d.fn.modes.pushParticles=function(e,a){d.tmp.pushing=!0;for(var t=0;t<e;t++)d.particles.array.push(new d.fn.particle(d.particles.color,d.particles.opacity.value,{x:a?a.pos_x:Math.random()*d.canvas.w,y:a?a.pos_y:Math.random()*d.canvas.h})),t==e-1&&(d.particles.move.enable||d.fn.particlesDraw(),d.tmp.pushing=!1)},d.fn.modes.removeParticles=function(e){d.particles.array.splice(0,e),d.particles.move.enable||d.fn.particlesDraw()},d.fn.modes.bubbleParticle=function(c){if(d.interactivity.events.onhover.enable&&isInArray("bubble",d.interactivity.events.onhover.mode)){var e=c.x-d.interactivity.mouse.pos_x,a=c.y-d.interactivity.mouse.pos_y,t=1-(o=Math.sqrt(e*e+a*a))/d.interactivity.modes.bubble.distance;function i(){c.opacity_bubble=c.opacity,c.radius_bubble=c.radius}if(o<=d.interactivity.modes.bubble.distance){if(0<=t&&"mousemove"==d.interactivity.status){if(d.interactivity.modes.bubble.size!=d.particles.size.value)if(d.interactivity.modes.bubble.size>d.particles.size.value){0<=(n=c.radius+d.interactivity.modes.bubble.size*t)&&(c.radius_bubble=n)}else{var s=c.radius-d.interactivity.modes.bubble.size,n=c.radius-s*t;c.radius_bubble=0<n?n:0}var r;if(d.interactivity.modes.bubble.opacity!=d.particles.opacity.value)if(d.interactivity.modes.bubble.opacity>d.particles.opacity.value)(r=d.interactivity.modes.bubble.opacity*t)>c.opacity&&r<=d.interactivity.modes.bubble.opacity&&(c.opacity_bubble=r);else(r=c.opacity-(d.particles.opacity.value-d.interactivity.modes.bubble.opacity)*t)<c.opacity&&r>=d.interactivity.modes.bubble.opacity&&(c.opacity_bubble=r)}}else i();"mouseleave"==d.interactivity.status&&i()}else if(d.interactivity.events.onclick.enable&&isInArray("bubble",d.interactivity.events.onclick.mode)){if(d.tmp.bubble_clicking){e=c.x-d.interactivity.mouse.click_pos_x,a=c.y-d.interactivity.mouse.click_pos_y;var o=Math.sqrt(e*e+a*a),l=((new Date).getTime()-d.interactivity.mouse.click_time)/1e3;l>d.interactivity.modes.bubble.duration&&(d.tmp.bubble_duration_end=!0),l>2*d.interactivity.modes.bubble.duration&&(d.tmp.bubble_clicking=!1,d.tmp.bubble_duration_end=!1)}function v(e,a,t,i,s){if(e!=a)if(d.tmp.bubble_duration_end)null!=t&&(r=e+(e-(i-l*(i-e)/d.interactivity.modes.bubble.duration)),"size"==s&&(c.radius_bubble=r),"opacity"==s&&(c.opacity_bubble=r));else if(o<=d.interactivity.modes.bubble.distance){if(null!=t)var n=t;else n=i;if(n!=e){var r=i-l*(i-e)/d.interactivity.modes.bubble.duration;"size"==s&&(c.radius_bubble=r),"opacity"==s&&(c.opacity_bubble=r)}}else"size"==s&&(c.radius_bubble=void 0),"opacity"==s&&(c.opacity_bubble=void 0)}d.tmp.bubble_clicking&&(v(d.interactivity.modes.bubble.size,d.particles.size.value,c.radius_bubble,c.radius,"size"),v(d.interactivity.modes.bubble.opacity,d.particles.opacity.value,c.opacity_bubble,c.opacity,"opacity"))}},d.fn.modes.repulseParticle=function(i){if(d.interactivity.events.onhover.enable&&isInArray("repulse",d.interactivity.events.onhover.mode)&&"mousemove"==d.interactivity.status){var e=i.x-d.interactivity.mouse.pos_x,a=i.y-d.interactivity.mouse.pos_y,t=Math.sqrt(e*e+a*a),s=e/t,n=a/t,r=clamp(1/(o=d.interactivity.modes.repulse.distance)*(-1*Math.pow(t/o,2)+1)*o*100,0,50),c={x:i.x+s*r,y:i.y+n*r};"bounce"==d.particles.move.out_mode?(0<c.x-i.radius&&c.x+i.radius<d.canvas.w&&(i.x=c.x),0<c.y-i.radius&&c.y+i.radius<d.canvas.h&&(i.y=c.y)):(i.x=c.x,i.y=c.y)}else if(d.interactivity.events.onclick.enable&&isInArray("repulse",d.interactivity.events.onclick.mode))if(d.tmp.repulse_finish||(d.tmp.repulse_count++,d.tmp.repulse_count==d.particles.array.length&&(d.tmp.repulse_finish=!0)),d.tmp.repulse_clicking){var o=Math.pow(d.interactivity.modes.repulse.distance/6,3),l=d.interactivity.mouse.click_pos_x-i.x,v=d.interactivity.mouse.click_pos_y-i.y,p=l*l+v*v,m=-o/p*1;p<=o&&function(){var e=Math.atan2(v,l);if(i.vx=m*Math.cos(e),i.vy=m*Math.sin(e),"bounce"==d.particles.move.out_mode){var a=i.x+i.vx,t=i.y+i.vy;a+i.radius>d.canvas.w?i.vx=-i.vx:a-i.radius<0&&(i.vx=-i.vx),t+i.radius>d.canvas.h?i.vy=-i.vy:t-i.radius<0&&(i.vy=-i.vy)}}()}else 0==d.tmp.repulse_clicking&&(i.vx=i.vx_i,i.vy=i.vy_i)},d.fn.modes.grabParticle=function(e){if(d.interactivity.events.onhover.enable&&"mousemove"==d.interactivity.status){var a=e.x-d.interactivity.mouse.pos_x,t=e.y-d.interactivity.mouse.pos_y,i=Math.sqrt(a*a+t*t);if(i<=d.interactivity.modes.grab.distance){var s=d.interactivity.modes.grab.line_linked.opacity-i/(1/d.interactivity.modes.grab.line_linked.opacity)/d.interactivity.modes.grab.distance;if(0<s){var n=d.particles.line_linked.color_rgb_line;d.canvas.ctx.strokeStyle="rgba("+n.r+","+n.g+","+n.b+","+s+")",d.canvas.ctx.lineWidth=d.particles.line_linked.width,d.canvas.ctx.beginPath(),d.canvas.ctx.moveTo(e.x,e.y),d.canvas.ctx.lineTo(d.interactivity.mouse.pos_x,d.interactivity.mouse.pos_y),d.canvas.ctx.stroke(),d.canvas.ctx.closePath()}}}},d.fn.vendors.eventsListeners=function(){"window"==d.interactivity.detect_on?d.interactivity.el=window:d.interactivity.el=d.canvas.el,(d.interactivity.events.onhover.enable||d.interactivity.events.onclick.enable)&&(d.interactivity.el.addEventListener("mousemove",function(e){if(d.interactivity.el==window)var a=e.clientX,t=e.clientY;else a=e.offsetX||e.clientX,t=e.offsetY||e.clientY;d.interactivity.mouse.pos_x=a,d.interactivity.mouse.pos_y=t,d.tmp.retina&&(d.interactivity.mouse.pos_x*=d.canvas.pxratio,d.interactivity.mouse.pos_y*=d.canvas.pxratio),d.interactivity.status="mousemove"}),d.interactivity.el.addEventListener("mouseleave",function(e){d.interactivity.mouse.pos_x=null,d.interactivity.mouse.pos_y=null,d.interactivity.status="mouseleave"})),d.interactivity.events.onclick.enable&&d.interactivity.el.addEventListener("click",function(){if(d.interactivity.mouse.click_pos_x=d.interactivity.mouse.pos_x,d.interactivity.mouse.click_pos_y=d.interactivity.mouse.pos_y,d.interactivity.mouse.click_time=(new Date).getTime(),d.interactivity.events.onclick.enable)switch(d.interactivity.events.onclick.mode){case"push":d.particles.move.enable?d.fn.modes.pushParticles(d.interactivity.modes.push.particles_nb,d.interactivity.mouse):1==d.interactivity.modes.push.particles_nb?d.fn.modes.pushParticles(d.interactivity.modes.push.particles_nb,d.interactivity.mouse):1<d.interactivity.modes.push.particles_nb&&d.fn.modes.pushParticles(d.interactivity.modes.push.particles_nb);break;case"remove":d.fn.modes.removeParticles(d.interactivity.modes.remove.particles_nb);break;case"bubble":d.tmp.bubble_clicking=!0;break;case"repulse":d.tmp.repulse_clicking=!0,d.tmp.repulse_count=0,d.tmp.repulse_finish=!1,setTimeout(function(){d.tmp.repulse_clicking=!1},1e3*d.interactivity.modes.repulse.duration)}})},d.fn.vendors.densityAutoParticles=function(){if(d.particles.number.density.enable){var e=d.canvas.el.width*d.canvas.el.height/1e3;d.tmp.retina&&(e/=2*d.canvas.pxratio);var a=e*d.particles.number.value/d.particles.number.density.value_area,t=d.particles.array.length-a;t<0?d.fn.modes.pushParticles(Math.abs(t)):d.fn.modes.removeParticles(t)}},d.fn.vendors.checkOverlap=function(e,a){for(var t=0;t<d.particles.array.length;t++){var i=d.particles.array[t],s=e.x-i.x,n=e.y-i.y;Math.sqrt(s*s+n*n)<=e.radius+i.radius&&(e.x=a?a.x:Math.random()*d.canvas.w,e.y=a?a.y:Math.random()*d.canvas.h,d.fn.vendors.checkOverlap(e))}},d.fn.vendors.createSvgImg=function(n){var e=d.tmp.source_svg.replace(/#([0-9A-F]{3,6})/gi,function(e,a,t,i){if(n.color.rgb)var s="rgba("+n.color.rgb.r+","+n.color.rgb.g+","+n.color.rgb.b+","+n.opacity+")";else s="hsla("+n.color.hsl.h+","+n.color.hsl.s+"%,"+n.color.hsl.l+"%,"+n.opacity+")";return s}),a=new Blob([e],{type:"image/svg+xml;charset=utf-8"}),t=window.URL||window.webkitURL||window,i=t.createObjectURL(a),s=new Image;s.addEventListener("load",function(){n.img.obj=s,n.img.loaded=!0,t.revokeObjectURL(i),d.tmp.count_svg++}),s.src=i},d.fn.vendors.destroypJS=function(){cancelAnimationFrame(d.fn.drawAnimFrame),t.remove(),pJSDom=null},d.fn.vendors.drawShape=function(e,a,t,i,s,n){var r=s*n,c=s/n,o=180*(c-2)/c,l=Math.PI-Math.PI*o/180;e.save(),e.beginPath(),e.translate(a,t),e.moveTo(0,0);for(var v=0;v<r;v++)e.lineTo(i,0),e.translate(i,0),e.rotate(l);e.fill(),e.restore()},d.fn.vendors.exportImg=function(){window.open(d.canvas.el.toDataURL("image/png"),"_blank")},d.fn.vendors.loadImg=function(e){if(d.tmp.img_error=void 0,""!=d.particles.shape.image.src)if("svg"==e){var a=new XMLHttpRequest;a.open("GET",d.particles.shape.image.src),a.onreadystatechange=function(e){4==a.readyState&&(200==a.status?(d.tmp.source_svg=e.currentTarget.response,d.fn.vendors.checkBeforeDraw()):(console.log("Error pJS - Image not found"),d.tmp.img_error=!0))},a.send()}else{var t=new Image;t.addEventListener("load",function(){d.tmp.img_obj=t,d.fn.vendors.checkBeforeDraw()}),t.src=d.particles.shape.image.src}else console.log("Error pJS - No image.src"),d.tmp.img_error=!0},d.fn.vendors.draw=function(){"image"==d.particles.shape.type?"svg"==d.tmp.img_type?d.tmp.count_svg>=d.particles.number.value?(d.fn.particlesDraw(),d.particles.move.enable?d.fn.drawAnimFrame=requestAnimFrame(d.fn.vendors.draw):cancelRequestAnimFrame(d.fn.drawAnimFrame)):d.tmp.img_error||(d.fn.drawAnimFrame=requestAnimFrame(d.fn.vendors.draw)):null!=d.tmp.img_obj?(d.fn.particlesDraw(),d.particles.move.enable?d.fn.drawAnimFrame=requestAnimFrame(d.fn.vendors.draw):cancelRequestAnimFrame(d.fn.drawAnimFrame)):d.tmp.img_error||(d.fn.drawAnimFrame=requestAnimFrame(d.fn.vendors.draw)):(d.fn.particlesDraw(),d.particles.move.enable?d.fn.drawAnimFrame=requestAnimFrame(d.fn.vendors.draw):cancelRequestAnimFrame(d.fn.drawAnimFrame))},d.fn.vendors.checkBeforeDraw=function(){"image"==d.particles.shape.type?"svg"==d.tmp.img_type&&null==d.tmp.source_svg?d.tmp.checkAnimFrame=requestAnimFrame(check):(cancelRequestAnimFrame(d.tmp.checkAnimFrame),d.tmp.img_error||(d.fn.vendors.init(),d.fn.vendors.draw())):(d.fn.vendors.init(),d.fn.vendors.draw())},d.fn.vendors.init=function(){d.fn.retinaInit(),d.fn.canvasInit(),d.fn.canvasSize(),d.fn.canvasPaint(),d.fn.particlesCreate(),d.fn.vendors.densityAutoParticles(),d.particles.line_linked.color_rgb_line=hexToRgb(d.particles.line_linked.color)},d.fn.vendors.start=function(){isInArray("image",d.particles.shape.type)?(d.tmp.img_type=d.particles.shape.image.src.substr(d.particles.shape.image.src.length-3),d.fn.vendors.loadImg(d.tmp.img_type)):d.fn.vendors.checkBeforeDraw()},d.fn.vendors.eventsListeners(),d.fn.vendors.start()};function hexToRgb(e){e=e.replace(/^#?([a-f\d])([a-f\d])([a-f\d])$/i,function(e,a,t,i){return a+a+t+t+i+i});var a=/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(e);return a?{r:parseInt(a[1],16),g:parseInt(a[2],16),b:parseInt(a[3],16)}:null}function clamp(e,a,t){return Math.min(Math.max(e,a),t)}function isInArray(e,a){return-1<a.indexOf(e)}Object.deepExtend=function(e,a){for(var t in a)a[t]&&a[t].constructor&&a[t].constructor===Object?(e[t]=e[t]||{},arguments.callee(e[t],a[t])):e[t]=a[t];return e},window.requestAnimFrame=window.requestAnimationFrame||window.webkitRequestAnimationFrame||window.mozRequestAnimationFrame||window.oRequestAnimationFrame||window.msRequestAnimationFrame||function(e){window.setTimeout(e,1e3/60)},window.cancelRequestAnimFrame=window.cancelAnimationFrame||window.webkitCancelRequestAnimationFrame||window.mozCancelRequestAnimationFrame||window.oCancelRequestAnimationFrame||window.msCancelRequestAnimationFrame||clearTimeout,window.pJSDom=[],window.particlesJS=function(e,a){"string"!=typeof e&&(a=e,e="particles-js"),e=e||"particles-js";var t=document.getElementById(e),i="particles-js-canvas-el",s=t.getElementsByClassName(i);if(s.length)for(;0<s.length;)t.removeChild(s[0]);var n=document.createElement("canvas");n.className=i,n.style.width="100%",n.style.height="100%",null!=document.getElementById(e).appendChild(n)&&pJSDom.push(new pJS(e,a))},window.particlesJS.load=function(e,a,t){window.particlesJS(e,a),t&&t()};

/* Config */
var config = {
  "particles": {
    "number": {
      "value": 80,
      "density": {
        "enable": true,
        "value_area": 800
      }
    },
    "color": {
      "value": "#ffffff"
    },
    "shape": {
      "type": "circle",
      "stroke": {
        "width": 0,
        "color": "#000000"
      },
      "polygon": {
        "nb_sides": 5
      },
      "image": {
        "src": "img/github.svg",
        "width": 100,
        "height": 100
      }
    },
    "opacity": {
      "value": 0.5,
      "random": false,
      "anim": {
        "enable": false,
        "speed": 1,
        "opacity_min": 0.1,
        "sync": false
      }
    },
    "size": {
      "value": 2,
      "random": true,
      "anim": {
        "enable": false,
        "speed": 40,
        "size_min": 0.1,
        "sync": false
      }
    },
    "line_linked": {
      "enable": true,
      "distance": 150,
      "color": "#ffffff",
      "opacity": 0.4,
      "width": 1
    },
    "move": {
      "enable": true,
      "speed": 2,
      "direction": "none",
      "random": false,
      "straight": false,
      "out_mode": "out",
      "bounce": false,
      "attract": {
        "enable": false,
        "rotateX": 600,
        "rotateY": 1200
      }
    }
  },
  "interactivity": {
    "detect_on": "canvas",
    "events": {
      "onhover": {
        "enable": true,
        "mode": "grab"
      },
      "onclick": {
        "enable": true,
        "mode": "push"
      },
      "resize": true
    },
    "modes": {
      "grab": {
        "distance": 150,
        "line_linked": {
          "opacity": 1
        }
      },
      "bubble": {
        "distance": 400,
        "size": 40,
        "duration": 2,
        "opacity": 8,
        "speed": 3
      },
      "repulse": {
        "distance": 200,
        "duration": 0.4
      },
      "push": {
        "particles_nb": 4
      },
      "remove": {
        "particles_nb": 2
      }
    }
  },
  "retina_detect": true
};


particlesJS.load('particles-js', config, function() {
   //foo
});

var videoInstance = new vidbg('.background-video-wrapper', {
  mp4: '//webdock.io/application/themes/webdock/img/webdock_promo_header.mp4', // URL or relative path to MP4 video
  poster: '//webdock.io/application/themes/webdock/img/video_poster.jpg', // URL or relative path to fallback image
  overlay: false, // Boolean to display the overlay or not
}, {
  // Attributes
});

</script>
  </body>
</html>
