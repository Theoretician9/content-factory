import React from 'react';
import Hero from '../components/landing/Hero';
import Features from '../components/landing/Features';
import Pricing from '../components/landing/Pricing';
import FAQ from '../components/landing/FAQ';
import ContactForm from '../components/landing/ContactForm';

const Landing = () => {
  return (
    <div className="min-h-screen">
      <Hero />
      <Features />
      <Pricing />
      <FAQ />
      <ContactForm />
    </div>
  );
};

export default Landing; 