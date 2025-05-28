import React from 'react';

const Hero = () => {
  return (
    <section className="bg-gradient-to-r from-blue-600 to-blue-800 text-white py-20">
      <div className="container mx-auto px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-6">
            HERO STATIC
          </h1>
          <p className="text-xl md:text-2xl mb-8 text-blue-100">
            SUBTITLE STATIC
          </p>
          <div className="space-x-4">
            <span>CTA STATIC</span>
            <span>LOGIN STATIC</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero; 