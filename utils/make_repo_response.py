from models.response.RepositoryResponse import RepositoryResponse


def make_repo_response(status: str, error_code: str, message: str, data: any = None) -> RepositoryResponse:

    return RepositoryResponse(status=status, error_code=error_code, message=message, data=data)
