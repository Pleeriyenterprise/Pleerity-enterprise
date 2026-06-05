const React = require('react');
export const useNavigate = () => jest.fn();
export const useParams = () => ({});
export const useLocation = () => ({ pathname: '/', search: '' });
export const MemoryRouter = ({ children }) => children;
export const Navigate = () => null;
export const Route = () => null;
export const Routes = ({ children }) => children;
export const Link = ({ children, to, ...props }) => React.createElement('a', { href: to, ...props }, children);
export const NavLink = ({ children, to, className, ...props }) => {
  const resolved = typeof className === 'function' ? className({ isActive: false }) : className;
  return React.createElement('a', { href: to, className: resolved, ...props }, children);
};
export const Outlet = () => null;
