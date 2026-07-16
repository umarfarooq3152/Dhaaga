import { Trefoil } from 'ldrs/react';
import 'ldrs/react/Trefoil.css';

interface LoaderProps {
  size?: string;
  color?: string;
  className?: string;
}

export default function Loader({ size = '18', color = '#003224', className }: LoaderProps) {
  return (
    <span className={className} role="status" aria-label="Loading">
      <Trefoil size={size} stroke="4" strokeLength="0.15" bgOpacity="0.1" speed="1.4" color={color} />
    </span>
  );
}
