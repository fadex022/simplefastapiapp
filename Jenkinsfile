pipeline {
    agent any

    environment {
        PROJECT = "fastapi"
        REPOSITORY = "simplefastapiapp"
        IMAGE = "$PROJECT/$REPOSITORY"
        REGISTRY_HOST = "https://harbor.devgauss.com"
    }

    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['development', 'staging', 'production'],
            description: 'Target environment'
        )
        booleanParam(
            name: 'SKIP_TESTS',
            defaultValue: false,
            description: 'Skip test execution'
        )
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set up Python') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    python3 -m pip install --upgrade pip

                    # Install Poetry
                    curl -sSL https://install.python-poetry.org | python3 -
                    export PATH="$HOME/.local/bin:$PATH"

                    # Configure Poetry to use the virtual environment
                    poetry config virtualenvs.create false

                    # Install dependencies using Poetry
                    poetry install
                '''
            }
        }

        /*
        stage('Code Quality Checks') {
            parallel {
                stage('Lint') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            export PATH="$HOME/.local/bin:$PATH"
                            poetry add --group dev flake8 black isort

                            # Run linting
                            poetry run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

                            # Check code formatting
                            poetry run black --check .

                            # Check import sorting
                            poetry run isort --check-only .
                        '''
                    }
                }

                stage('Security Scan') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            export PATH="$HOME/.local/bin:$PATH"
                            poetry add --group dev bandit safety

                            # Run security checks
                            poetry run bandit -r . -x tests/

                            # Check for known vulnerabilities
                            poetry run safety check
                        '''
                    }
                }
            }
        }
        */

        stage('Run Tests') {
            when {
                expression { return !params.SKIP_TESTS }
            }
            steps {
                sh '''
                    . venv/bin/activate
                    export PATH="$HOME/.local/bin:$PATH"

                    # Install additional test dependencies if needed
                    poetry add --group dev pytest-xdist pytest-cov

                    # Run tests with JUnit report for better visualization in Jenkins
                    poetry run pytest --junitxml=test-results.xml

                    # Run tests with coverage reporting
                    poetry run pytest \
                        --cov=. \
                        --cov-report=xml:coverage.xml \
                        --cov-report=html:htmlcov \
                        --cov-report=term \
                        --cov-fail-under=65
                '''
            }
            post {
                always {
                    // Archive test artifacts and coverage reports
                    archiveArtifacts artifacts: 'coverage.xml,htmlcov/**/*,test-results.xml', allowEmptyArchive: true

                    // Publish JUnit test results
                    junit 'test-results.xml'

                    // Publish HTML coverage report
                    publishHTML(target: [
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'htmlcov',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        stage('Build and Push Docker Image') {
            when {
                expression {
                    return env.CHANGE_ID == null // Skip for pull requests
                }
            }
            steps {
                script {
                    def image = docker.build("$IMAGE:${env.BUILD_ID}")
                    docker.withRegistry("$REGISTRY_HOST", 'registry-credentials-fadel') { 
                        image.push()
                        image.push('latest')
                    }
                }
            }
        }

        stage('Update Kubernetes Deployment') {
            when {
                expression {
                    return env.CHANGE_ID == null // Skip for pull requests
                }
            }
            steps {
                script {
                    // Update the image tag in the deployment.yaml file
                    sh """
                        sed -i 's|image: harbor.devgauss.com/fastapi/simplefastapiapp:.*|image: harbor.devgauss.com/fastapi/simplefastapiapp:${env.BUILD_ID}|' kubernetes/deployment.yaml
                    """

                    // Commit and push the changes
                    withCredentials([usernamePassword(credentialsId: 'git-credentials', passwordVariable: 'GIT_PASSWORD', usernameVariable: 'GIT_USERNAME')]) {
                        sh """
                            git config user.email "jenkins@devgauss.com"
                            git config user.name "Jenkins"

                            # Check if there are changes to commit
                            if git diff --quiet kubernetes/deployment.yaml; then
                                echo "No changes to deployment.yaml, skipping commit and push"
                            else
                                git add kubernetes/deployment.yaml
                                git commit -m "Update deployment image to ${env.BUILD_ID} [skip ci]"

                                # Get the repository URL from git config
                                REPO_URL=\$(git config --get remote.origin.url)

                                # Handle different URL formats (HTTPS or SSH)
                                if [[ \$REPO_URL == https://* ]]; then
                                    # For HTTPS URLs
                                    REPO_URL_WITH_CREDS=\$(echo \$REPO_URL | sed 's|https://|https://${GIT_USERNAME}:${GIT_PASSWORD}@|')
                                elif [[ \$REPO_URL == git@* ]]; then
                                    # For SSH URLs, convert to HTTPS with credentials
                                    REPO_URL_WITH_CREDS=\$(echo \$REPO_URL | sed 's|git@\\(.*\\):\\(.*\\)|https://${GIT_USERNAME}:${GIT_PASSWORD}@\\1/\\2|')
                                else
                                    echo "Unsupported Git URL format"
                                    exit 1
                                fi

                                git push \$REPO_URL_WITH_CREDS HEAD:${env.BRANCH_NAME}
                            fi
                        """
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo 'Pipeline succeeded!'
        }
        failure {
            echo 'Pipeline failed!'
        }
    }
}
