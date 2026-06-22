class MLflowTracker:
    def __init__(self, tracking_uri: str = "mlruns", experiment_name: str = "algocore-ml"):
        import mlflow
        import mlflow.sklearn
        self._mlflow = mlflow
        self._mlflow_sklearn = mlflow.sklearn
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        self._run_id: str | None = None

    def start_run(self, run_name: str) -> str:
        run = self._mlflow.start_run(run_name=run_name)
        self._run_id = run.info.run_id
        return self._run_id

    def log_params(self, params: dict) -> None:
        self._mlflow.log_params(params)

    def log_metrics(self, metrics: dict) -> None:
        self._mlflow.log_metrics(metrics)

    def log_model(self, model, artifact_path: str) -> None:
        self._mlflow_sklearn.log_model(model, artifact_path)

    def register_model(self, run_id: str, artifact_path: str, name: str) -> None:
        model_uri = f"runs:/{run_id}/{artifact_path}"
        self._mlflow.register_model(model_uri, name)

    def end_run(self) -> None:
        self._mlflow.end_run()
        self._run_id = None
