import React from 'react';
import twinImage from '../assets/images/maitri_station_twin_1789652424632.jpg';

interface StationPageStripProps {
  title: string;
  subtitle: string;
  right?: React.ReactNode;
}

export const StationPageStrip: React.FC<StationPageStripProps> = ({ title, subtitle, right }) => (
  <section
    className="station-page-strip"
    style={{
      backgroundImage: `linear-gradient(90deg, rgba(2,7,18,.96) 0%, rgba(2,12,27,.72) 48%, rgba(2,12,27,.38) 100%), url(${twinImage})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center 58%',
    }}
  >
    <div className="h-full min-h-[112px] px-6 py-5 flex items-center justify-between gap-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-wide text-white">{title}</h1>
        <p className="text-sm text-cyan-300/90 mt-1">{subtitle}</p>
      </div>
      {right}
    </div>
  </section>
);
