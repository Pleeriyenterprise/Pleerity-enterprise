const React = require('react');
export const useNavigate = () => jest.fn();
export const useParams = () => ({});
export const useLocation = () => ({ pathname: '/', search: '' });
export const MemoryRouter = ({ children }) => children;
export const Navigate = () => null;
export const Route = () => null;
export const Routes = ({ children }) => children;
export const Link = ({ children, to }) => React.createElement('a', { href: to }, children);
