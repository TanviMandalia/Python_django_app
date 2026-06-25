import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ArrowRight, Calendar, Phone, Check } from 'lucide-react';

const servicesData = [
  {
    category: "Pain Management",
    treatments: ["Neck Pain", "Back Pain", "Slip Disc", "Sciatica", "Shoulder Pain", "Knee Pain", "Joint Pain", "Muscle Spasm"]
  },
  {
    category: "Frozen Shoulder & Shoulder Rehab",
    treatments: ["Frozen Shoulder", "Shoulder Stiffness", "Rotator Cuff", "Hydrodilatation Rehab"]
  },
  {
    category: "Spine & Nerve Conditions",
    treatments: ["Cervical Spondylosis", "Lumbar Spondylosis", "Sciatica", "Nerve Compression", "Posture Correction"]
  },
  {
    category: "Sports & Orthopaedic",
    treatments: ["Sports Injury", "ACL Rehab", "Meniscus Injury", "Fracture Rehab", "Ligament", "Post-Surgery Physio"]
  },
  {
    category: "Neurological",
    treatments: ["Stroke Rehab", "Paralysis Physio", "Parkinson's", "Balance & Gait Training"]
  },
  {
    category: "Women's Health",
    treatments: ["Pregnancy Physio", "Postpartum Recovery", "Pelvic Floor"]
  },
  {
    category: "Advanced Treatments",
    treatments: ["Dry Needling", "Cupping", "Kinesiology Taping", "Electrotherapy", "IFT/TENS", "Ultrasound", "Manual Therapy", "Myofascial Release"]
  },
  {
    category: "Mobility & Fitness",
    treatments: ["Strengthening", "Flexibility", "Posture Correction", "Ergonomics", "Functional Rehab"]
  },
  {
    category: "Home Care",
    treatments: ["Home Visit Physio", "Elderly Home Physio", "Post-Surgery Home Rehab"]
  }
];

const steps = [
  {
    num: "01",
    title: "Initial Consultation",
    desc: "A thorough assessment of your condition, medical history, and physical limitations to understand the root cause."
  },
  {
    num: "02",
    title: "Personalized Plan",
    desc: "Developing a tailored treatment protocol focusing on immediate relief and long-term recovery goals."
  },
  {
    num: "03",
    title: "Active Treatment",
    desc: "Implementation of advanced therapies, manual techniques, and guided exercises in our state-of-the-art clinic."
  },
  {
    num: "04",
    title: "Ongoing Maintenance",
    desc: "Post-recovery strengthening and ergonomic advice to prevent future injuries and maintain peak mobility."
  }
];

export function CleanMinimal() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggleAccordion = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <div className="min-h-screen bg-white text-[#2C2C2C] font-sans selection:bg-[#F5C518] selection:text-[#2C2C2C]">
      {/* Google Fonts inline import for mockup only */}
      <style dangerouslySetInnerHTML={{__html: `
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Inter:wght@300;400;500;600&display=swap');
        .font-serif { font-family: 'Playfair Display', serif; }
        .font-sans { font-family: 'Inter', sans-serif; }
      `}} />

      {/* Hero Section */}
      <section className="relative pt-32 pb-24 px-6 md:px-12 max-w-7xl mx-auto text-center">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-64 bg-gradient-to-b from-[#F5C518]/10 to-transparent -z-10 rounded-b-full blur-3xl opacity-50 pointer-events-none"></div>
        <span className="inline-block py-1 px-3 border border-[#F5C518]/30 rounded-full text-sm font-medium tracking-wide text-[#F5C518] uppercase mb-8">
          Dr. Dhvani Patalia Physio-Rehab
        </span>
        <h1 className="font-serif text-5xl md:text-7xl font-medium leading-tight mb-8 text-[#2C2C2C]">
          Restoring Movement.<br className="hidden md:block"/> Elevating Life.
        </h1>
        <p className="text-lg md:text-xl text-gray-500 max-w-2xl mx-auto font-light leading-relaxed mb-12">
          Comprehensive physiotherapy and rehabilitation services designed to heal the root cause, not just the symptoms.
        </p>
      </section>

      {/* Services Section */}
      <section className="py-24 px-6 md:px-12 max-w-6xl mx-auto border-t border-gray-100">
        <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-6">
          <div className="max-w-xl">
            <h2 className="font-serif text-4xl md:text-5xl font-medium text-[#2C2C2C] mb-4">Our Expertise</h2>
            <p className="text-gray-500 font-light">Explore our comprehensive range of specialized physiotherapy services and advanced treatments.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6 items-start">
          {servicesData.map((service, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div key={idx} className="border-b border-gray-200 group">
                <button 
                  onClick={() => toggleAccordion(idx)}
                  className="w-full py-6 flex justify-between items-center text-left focus:outline-none"
                >
                  <h3 className="font-serif text-2xl group-hover:text-[#F5C518] transition-colors duration-300">
                    {service.category}
                  </h3>
                  <span className={\`transform transition-transform duration-300 \${isOpen ? 'rotate-180 text-[#F5C518]' : 'text-gray-400'}\`}>
                    <ChevronDown className="w-5 h-5" strokeWidth={1.5} />
                  </span>
                </button>
                
                <div 
                  className={\`overflow-hidden transition-all duration-500 ease-in-out \${isOpen ? 'max-h-96 opacity-100 pb-8' : 'max-h-0 opacity-0'}\`}
                >
                  <div className="pl-6 border-l-2 border-[#F5C518]">
                    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-y-3 gap-x-4">
                      {service.treatments.map((treatment, tIdx) => (
                        <li key={tIdx} className="flex items-center text-gray-600 font-light text-sm">
                          <Check className="w-4 h-4 text-[#F5C518] mr-2 flex-shrink-0" strokeWidth={2} />
                          {treatment}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-24 px-6 md:px-12 bg-[#fafafa]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="font-serif text-4xl md:text-5xl font-medium text-[#2C2C2C] mb-4">Your Path to Recovery</h2>
            <p className="text-gray-500 font-light max-w-2xl mx-auto">Our structured approach ensures every patient receives focused, effective, and continuous care.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 lg:gap-8">
            {steps.map((step, idx) => (
              <div key={idx} className="relative group">
                <div className="text-7xl font-serif font-bold text-[#F5C518]/20 mb-6 transition-colors duration-500 group-hover:text-[#F5C518]/40">
                  {step.num}
                </div>
                <h3 className="text-xl font-medium text-[#2C2C2C] mb-4">{step.title}</h3>
                <p className="text-gray-500 font-light text-sm leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 md:px-12 max-w-5xl mx-auto text-center">
        <div className="border border-gray-100 bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-12 md:p-20 rounded-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-[#F5C518]"></div>
          <h2 className="font-serif text-4xl md:text-5xl font-medium text-[#2C2C2C] mb-6">Ready to live pain-free?</h2>
          <p className="text-gray-500 font-light max-w-xl mx-auto mb-10 text-lg">
            Book your consultation today and take the first step towards a healthier, more active life.
          </p>
          <div className="flex flex-col sm:flex-row justify-center items-center gap-4">
            <button className="w-full sm:w-auto px-8 py-4 bg-[#2C2C2C] text-white rounded font-medium hover:bg-black transition-colors duration-300 flex items-center justify-center">
              <Calendar className="w-5 h-5 mr-2" />
              Book Appointment
            </button>
            <button className="w-full sm:w-auto px-8 py-4 bg-transparent border border-[#2C2C2C] text-[#2C2C2C] rounded font-medium hover:bg-[#2C2C2C] hover:text-white transition-all duration-300 flex items-center justify-center">
              <Phone className="w-5 h-5 mr-2" />
              +91 98765 43210
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
