export default function GradientButton({
  children,
  variant = "primary", // primary | ai | secondary | danger
  className = "",
  ...rest
}) {
  return (
    <button className={`gbtn gbtn-${variant} ${className}`} {...rest}>
      {children}
    </button>
  );
}
